"""Render deterministic reports and publish the three files as one directory."""

import csv
import html
import io
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .data import DataError


def _markdown(text):
    single_line = html.escape(" ".join(text.split()), quote=False)
    return re.sub(r"([\\|*\x60_\[\]~])", r"\\\1", single_line)


def _spreadsheet_text(text):
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(
        ("=", "+", "-", "@")
    ):
        return "'" + text
    return text


def render(report: dict) -> dict[str, bytes]:
    csv_buffer = io.StringIO(newline="")
    fields = (
        "rank",
        "firm",
        "name",
        "visibility_pct",
        "pooled_mention_pct",
        "analyzed_answers",
        "mentioned",
        "officially_cited",
        "mentioned_and_cited",
    )
    writer = csv.DictWriter(csv_buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in report["firms"]:
        cells = {k: row[k] for k in fields}
        cells["name"] = _spreadsheet_text(cells["name"])
        writer.writerow(cells)

    coverage = report["coverage"]
    budget = report["budget"]
    lines = [
        "# Visibility report",
        "",
        _markdown(report["dataset"]),
        "",
        f"Analyzed {coverage['analyzed']} of {coverage['expected']} expected engine–prompt pairs. "
        f"{coverage['budget_skipped']} supplied answers exceeded the remaining reservation budget. "
        f"{coverage['missing']} pairs had no supplied answer.",
        "",
        f"Modeled spend was USD {budget['modeled_spend_usd']} against a USD {budget['limit_usd']} limit. "
        f"USD {budget['remaining_usd']} remained.",
        "",
        "| Rank | Firm | Visibility (%) | Answers mentioning | Answers citing an official domain | Both |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report["firms"]:
        lines.append(
            f"| {row['rank'] or '—'} | {_markdown(row['name'])} | {row['visibility_pct'] or '—'} "
            f"| {row['mentioned']} | {row['officially_cited']} | {row['mentioned_and_cited']} |"
        )
    lines += [
        "",
        "Visibility is the mean of the mention rates for the individual engines. "
        "An engine with zero analyzed answers leaves the index and ranks undefined.",
        "",
        "| Engine | Expected | Supplied | Analyzed | Budget skipped | Missing |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for engine, row in report["engine_coverage"].items():
        lines.append(
            f"| {_markdown(engine)} | {row['expected']} | {row['supplied']} | {row['analyzed']} "
            f"| {row['budget_skipped']} | {row['missing']} |"
        )
    lines += [
        "",
        "Each input line has a budget decision in the JSON report. Analyzed rows include the matched "
        "firms, normalized citation URLs and their attributed owners. [JSON audit](report.json) · [Firm table](firms.csv)",
        "",
    ]
    return {
        "report.json": (
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        ).encode(),
        "firms.csv": csv_buffer.getvalue().encode(),
        "index.md": "\n".join(lines).encode(),
    }


def _matches(path: Path, files: dict[str, bytes]) -> bool:
    if (
        path.is_symlink()
        or not path.is_dir()
        or {p.name for p in path.iterdir()} != files.keys()
    ):
        return False
    for name, content in files.items():
        stored = path / name
        if (
            stored.is_symlink()
            or not stored.is_file()
            or stored.stat().st_size != len(content)
        ):
            return False
        if stored.read_bytes() != content:
            return False
    return True


def publish(path: Path, files: dict[str, bytes]) -> None:
    def verify_existing():
        if not _matches(path, files):
            raise DataError(
                f"{path} contains different output; choose a new report directory"
            )

    if path.exists() or path.is_symlink():
        verify_existing()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent, prefix=".amlaw-") as stage:
        ready = Path(stage) / "report"
        ready.mkdir()
        for name, content in files.items():
            (ready / name).write_bytes(content)
        try:
            ready.rename(path)
        except OSError:
            # Another identical run can publish first. A different result must remain intact.
            if not (path.exists() or path.is_symlink()):
                raise
            verify_existing()
