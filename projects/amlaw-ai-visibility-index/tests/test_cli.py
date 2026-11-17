import csv
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from test_data import answer, catalog, write_data


class CommandTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.data = self.home / "inputs"
        self.data.mkdir()
        self.out = self.home / "result"
        write_data(self.data, catalog(), [answer()])
        self.cmd = [
            sys.executable,
            "-m",
            "visibility_index",
            "--data",
            str(self.data),
            "--out",
            str(self.out),
        ]

    def call(self, budget="1"):
        return subprocess.run(
            [*self.cmd, "--budget-usd", budget], capture_output=True, text=True
        )

    def test_normal_entrypoint_and_identical_concurrent_retries(self):
        jobs = [
            subprocess.Popen(
                [*self.cmd, "--budget-usd", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(3)
        ]
        for job in jobs:
            out, err = job.communicate(timeout=15)
            self.assertEqual(job.returncode, 0, err)
            self.assertIn(b"1/1", out)
        self.assertEqual(
            sorted(p.name for p in self.out.iterdir()),
            ["firms.csv", "index.md", "report.json"],
        )
        content = (self.out / "report.json").read_bytes()
        self.assertEqual(json.loads(content)["firms"][0]["rank"], 1)
        self.assertEqual(self.call().returncode, 0)
        self.assertEqual((self.out / "report.json").read_bytes(), content)
        self.assertEqual(list(self.home.glob(".amlaw-*")), [])

    def test_conflicting_replay_preserves_the_previous_bundle(self):
        self.assertEqual(self.call().returncode, 0)
        original = {p.name: p.read_bytes() for p in self.out.iterdir()}
        error = self.call("0")
        self.assertEqual(error.returncode, 2)
        self.assertIn("different output", error.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in self.out.iterdir()}, original)

    def test_validation_precedes_output_and_includes_input_location(self):
        with (self.data / "answers.jsonl").open("a", encoding="utf-8") as f:
            f.write("{broken\n")
        error = self.call()
        self.assertEqual(error.returncode, 2)
        self.assertIn("answers.jsonl:2", error.stderr)
        self.assertFalse(self.out.exists())

    def test_exports_keep_firm_names_readable_and_csv_text_safe(self):
        spec = catalog()
        spec["firms"][0]["name"] = "=Example | Group"
        write_data(self.data, spec, [answer(text="Example Group")])
        self.assertEqual(self.call().returncode, 0)
        raw = json.loads((self.out / "report.json").read_text())
        self.assertEqual(raw["firms"][0]["name"], "=Example | Group")
        table = list(csv.DictReader(StringIO((self.out / "firms.csv").read_text())))
        self.assertEqual(table[0]["name"], "'=Example | Group")
        self.assertIn(r"Example \| Group", (self.out / "index.md").read_text())
