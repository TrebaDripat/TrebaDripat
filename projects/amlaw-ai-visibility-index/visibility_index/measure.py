"""Score only admitted answers and keep enough information to audit every decision."""

from collections import Counter, defaultdict
from fractions import Fraction
import re

from .data import Dataset, Firm, words


# Link labels remain in prose. URL hosts and paths cannot create name mentions.
_LINK = re.compile(
    r"https?://[^\s<>()\[\]]+|(?<![\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}"
    r"(?::[0-9]+)?(?:[/?#][^\s<>()\[\]]*)?",
    re.IGNORECASE,
)


def usd(nanos: int) -> str:
    whole, fraction = divmod(nanos, 1_000_000_000)
    return f"{whole}.{fraction:09d}".rstrip("0").rstrip(".")


def percent(share: Fraction | None) -> str | None:
    if share is None:
        return None
    basis_points, remainder = divmod(share.numerator * 10_000, share.denominator)
    if 2 * remainder >= share.denominator:
        basis_points += 1
    return f"{basis_points // 100}.{basis_points % 100:02d}"


class Attribution:
    def __init__(self, firms: dict[str, Firm]):
        self.by_first_word = defaultdict(list)
        self.by_host = {}
        for firm in firms.values():
            for alias in firm.aliases:
                self.by_first_word[alias[0]].append((alias, firm.id))
            for host in firm.domains:
                self.by_host[host] = firm.id
        for candidates in self.by_first_word.values():
            candidates.sort(key=lambda pair: -len(pair[0]))

    def mentions(self, text: str) -> list[str]:
        result = set()
        for segment in _LINK.split(text):
            tokens = words(segment)
            offset = 0
            while offset < len(tokens):
                for alias, firm in self.by_first_word.get(tokens[offset], ()):
                    if tokens[offset : offset + len(alias)] == alias:
                        result.add(firm)
                        offset += len(alias)
                        break
                else:
                    offset += 1
        return sorted(result)

    def owner(self, host: str) -> str | None:
        # Walk DNS labels from the most specific host to its registered parent.
        labels = host.split(".")
        for start in range(len(labels) - 1):
            owner = self.by_host.get(".".join(labels[start:]))
            if owner is not None:
                return owner
        return None


def _firm_rows(data, counts, coverage):
    ranked = []
    total_answers = sum(row["analyzed"] for row in coverage.values())
    for firm in data.firms.values():
        totals = Counter()
        by_engine = {}
        shares = []
        for engine, sample in coverage.items():
            cell = counts[firm.id, engine]
            totals.update(cell)
            n = sample["analyzed"]
            share = Fraction(cell["mentioned"], n) if n else None
            if share is not None:
                shares.append(share)
            by_engine[engine] = {
                "answers": n,
                "mentioned": cell["mentioned"],
                "officially_cited": cell["cited"],
                "mentioned_and_cited": cell["supported"],
                "mention_pct": percent(share),
            }
        balanced = (
            sum(shares, Fraction()) / len(shares)
            if len(shares) == len(coverage)
            else None
        )
        pooled = Fraction(totals["mentioned"], total_answers) if total_answers else None
        row = {
            "firm": firm.id,
            "name": firm.name,
            "rank": None,
            "visibility_pct": percent(balanced),
            "analyzed_answers": total_answers,
            "mentioned": totals["mentioned"],
            "officially_cited": totals["cited"],
            "mentioned_and_cited": totals["supported"],
            "pooled_mention_pct": percent(pooled),
            "by_engine": by_engine,
        }
        ranked.append((balanced, row))
    # An engine with no analyzed answers makes the balanced score undefined for all firms.
    ranked.sort(key=lambda item: (-(item[0] or Fraction()), item[1]["firm"]))
    previous = None
    rank = None
    for position, (score, row) in enumerate(ranked, 1):
        if score is not None and score != previous:
            rank = position
        row["rank"] = rank
        previous = score
    return [row for _, row in ranked]


def run(data: Dataset, budget_nanos: int) -> dict:
    if type(budget_nanos) is not int or budget_nanos < 0:
        raise ValueError("budget must be a nonnegative integer number of nanodollars")
    attribution = Attribution(data.firms)
    coverage = {
        engine: {
            "expected": len(data.prompts),
            "supplied": 0,
            "analyzed": 0,
            "budget_skipped": 0,
        }
        for engine in data.engines
    }
    observations = []
    counts = defaultdict(Counter)
    spent = 0
    for answer in data.answers:
        engine = data.engines[answer.engine]
        sample = coverage[engine.id]
        sample["supplied"] += 1
        input_cost = answer.input_tokens * engine.input_nanos
        reservation = input_cost + answer.max_output_tokens * engine.output_nanos
        audit = {
            "input_line": answer.line,
            "prompt": answer.prompt,
            "engine": engine.id,
            "reservation_usd": usd(reservation),
        }
        if reservation > budget_nanos - spent:
            sample["budget_skipped"] += 1
            audit.update(status="budget_skipped", modeled_cost_usd="0")
        else:
            cost = input_cost + answer.output_tokens * engine.output_nanos
            spent += cost
            sample["analyzed"] += 1
            mentioned = attribution.mentions(answer.text)
            links = [
                {"url": c.url, "firm": attribution.owner(c.host)}
                for c in answer.citations
            ]
            cited = {c["firm"] for c in links if c["firm"] is not None}
            for firm in mentioned:
                counts[firm, engine.id]["mentioned"] += 1
                if firm in cited:
                    counts[firm, engine.id]["supported"] += 1
            for firm in cited:
                counts[firm, engine.id]["cited"] += 1
            audit.update(
                status="analyzed",
                modeled_cost_usd=usd(cost),
                mentions=mentioned,
                citations=links,
            )
        audit["remaining_usd"] = usd(budget_nanos - spent)
        observations.append(audit)
    for sample in coverage.values():
        sample["missing"] = sample["expected"] - sample["supplied"]
    totals = {
        field: sum(row[field] for row in coverage.values())
        for field in ("expected", "supplied", "analyzed", "budget_skipped", "missing")
    }
    return {
        "schema_version": 1,
        "dataset": data.label,
        "source_sha256": data.sha256,
        "budget": {
            "limit_usd": usd(budget_nanos),
            "modeled_spend_usd": usd(spent),
            "remaining_usd": usd(budget_nanos - spent),
        },
        "coverage": totals,
        "engine_coverage": coverage,
        "firms": _firm_rows(data, counts, coverage),
        "observations": observations,
    }
