import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_data import answer, catalog, write_data
from visibility_index.data import load_dataset
from visibility_index.measure import run
from visibility_index.reporting import render


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "examples/demo"


class RecordedDemoTests(unittest.TestCase):
    def test_matches_the_explicit_labels_for_every_fixture(self):
        labels = json.loads((INPUTS / "labels.json").read_text(encoding="utf-8"))
        result = run(load_dataset(INPUTS), 25_000_000)
        observed = {
            f"{r['engine']}/{r['prompt']}": {
                "mentions": r["mentions"],
                "official_domains": sorted(
                    {c["firm"] for c in r["citations"] if c["firm"]}
                ),
            }
            for r in result["observations"]
        }
        self.assertEqual(observed, labels)
        self.assertEqual(len(observed), 17)
        links = [c for row in result["observations"] for c in row["citations"]]
        self.assertEqual(
            (len(links), sum(c["firm"] is not None for c in links)), (25, 17)
        )

    def test_replay_agrees_with_independent_decimal_accounting(self):
        spec = json.loads((INPUTS / "catalog.json").read_text(encoding="utf-8"))
        rates = {
            e["id"]: (
                Decimal(e["input_usd_per_million"]),
                Decimal(e["output_usd_per_million"]),
            )
            for e in spec["engines"]
        }
        source = [
            json.loads(line)
            for line in (INPUTS / "answers.jsonl")
            .read_text(encoding="utf-8")
            .split("\n")
            if line
        ]
        for limit in ["0.025", "0.004"]:
            with self.subTest(limit=limit):
                report = run(load_dataset(INPUTS), int(Decimal(limit) * 1_000_000_000))
                balance = Decimal(limit)
                for original, row in zip(source, report["observations"], strict=True):
                    input_rate, output_rate = rates[original["engine"]]
                    input_cost = input_rate * original["input_tokens"] / 1_000_000
                    worst = (
                        input_cost
                        + output_rate * original["max_output_tokens"] / 1_000_000
                    )
                    self.assertEqual(Decimal(row["reservation_usd"]), worst)
                    if worst <= balance:
                        cost = (
                            input_cost
                            + output_rate * original["output_tokens"] / 1_000_000
                        )
                        self.assertEqual(row["status"], "analyzed")
                    else:
                        cost = Decimal(0)
                        self.assertEqual(row["status"], "budget_skipped")
                    balance -= cost
                    self.assertEqual(Decimal(row["modeled_cost_usd"]), cost)
                    self.assertEqual(Decimal(row["remaining_usd"]), balance)
                self.assertGreaterEqual(balance, 0)
                self.assertEqual(Decimal(report["budget"]["remaining_usd"]), balance)

    def test_complete_and_tight_budget_outputs_reproduce_byte_for_byte(self):
        for directory, nanos, answers in [
            ("demo", 25_000_000, 17),
            ("budgeted", 4_000_000, 10),
        ]:
            with self.subTest(directory=directory):
                result = run(load_dataset(INPUTS), nanos)
                self.assertEqual(
                    result["coverage"],
                    {
                        "expected": 18,
                        "supplied": 17,
                        "analyzed": answers,
                        "budget_skipped": 17 - answers,
                        "missing": 1,
                    },
                )
                files = render(result)
                stored = {
                    p.name: p.read_bytes()
                    for p in (ROOT / "reports" / directory).iterdir()
                }
                self.assertEqual(stored, files)

    def test_unicode_line_separator_inside_recorded_text_is_not_a_new_record(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            write_data(path, catalog(), [])
            body = json.dumps(answer(text="Pine\u2028and Lake"), ensure_ascii=False)
            (path / "answers.jsonl").write_text(body + "\r\n", encoding="utf-8")
            rows = run(load_dataset(path), 1_000_000)["observations"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["mentions"], ["pine"])
