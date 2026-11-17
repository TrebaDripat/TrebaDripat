from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_data import answer, catalog, write_data
from visibility_index.data import load_dataset
from visibility_index.measure import Attribution, percent, run


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def dataset(self, spec, answers):
        write_data(self.directory, spec, answers)
        return load_dataset(self.directory)

    def test_alias_and_domain_attribution_have_different_rules(self):
        spec = catalog()
        spec["firms"].append(
            {
                "id": "tax",
                "name": "Pine and Lake Tax",
                "aliases": ["PL Tax"],
                "domains": ["tax.pine.example"],
            }
        )
        match = Attribution(self.dataset(spec, []).firms)
        self.assertEqual(
            match.mentions("PİNELESS. ＰＬ Tax and pine & lake tax."), ["tax"]
        )
        self.assertEqual(
            match.mentions("[Pine & Lake](https://tax.pine.example/PL-Tax)"), ["pine"]
        )
        self.assertEqual(
            match.mentions(
                "pine-and-lake.example and https://other.example/Pine-and-Lake"
            ),
            [],
        )
        self.assertEqual(
            match.mentions("Pine and Lakeshore; Pine https://other.example and Lake"),
            [],
        )
        self.assertEqual(match.owner("www.tax.pine.example"), "tax")
        self.assertEqual(match.owner("news.pine.example"), "pine")
        self.assertIsNone(match.owner("pine.example.impostor.example"))

    def test_budget_admission_uses_ceiling_then_releases_unused_reservation(self):
        spec = catalog()
        spec["prompts"] += [
            {"id": "two", "text": "Two?"},
            {"id": "three", "text": "Three?"},
        ]
        rows = [
            answer(),
            answer(prompt="two", max_output_tokens=30),
            answer(prompt="three", max_output_tokens=4),
        ]
        data = self.dataset(spec, rows)
        result = run(data, 21_500)
        self.assertEqual(
            [r["status"] for r in result["observations"]],
            ["analyzed", "budget_skipped", "analyzed"],
        )
        self.assertEqual(
            result["budget"],
            {
                "limit_usd": "0.0000215",
                "modeled_spend_usd": "0.000011",
                "remaining_usd": "0.0000105",
            },
        )
        self.assertEqual(result["coverage"]["analyzed"], 2)
        self.assertEqual(result["coverage"]["budget_skipped"], 1)
        self.assertEqual(result["firms"][0]["visibility_pct"], "100.00")
        self.assertEqual(run(data, 5_499)["coverage"]["analyzed"], 0)

    def test_each_answer_counts_once_and_link_only_answers_are_distinct(self):
        spec = catalog()
        spec["prompts"] += [
            {"id": "two", "text": "Two?"},
            {"id": "three", "text": "Three?"},
        ]
        data = self.dataset(
            spec,
            [
                answer(
                    text="Pine and Lake. Pine & Lake!",
                    citations=[
                        "https://pine.example/x",
                        "https://PINE.example:443/x#top",
                        "https://sub.pine.example/y",
                    ],
                ),
                answer(
                    prompt="two",
                    text="https://other.example/Pine-and-Lake",
                    citations=["https://pine.example"],
                ),
            ],
        )
        result = run(data, 1_000_000)
        row = result["firms"][0]
        self.assertEqual(
            (row["mentioned"], row["officially_cited"], row["mentioned_and_cited"]),
            (1, 2, 1),
        )
        self.assertEqual(row["pooled_mention_pct"], "50.00")
        self.assertEqual(result["coverage"]["missing"], 1)
        self.assertEqual(len(result["observations"][0]["citations"]), 2)

    def test_balanced_score_gives_each_engine_equal_weight_and_exact_ties_share_rank(
        self,
    ):
        spec = catalog()
        spec["engines"].append(dict(spec["engines"][0], id="other"))
        spec["firms"].append(
            {
                "id": "oak",
                "name": "Oak Ridge",
                "aliases": [],
                "domains": ["oak.example"],
            }
        )
        spec["prompts"].append({"id": "two", "text": "Two?"})
        rows = [
            answer(text="Pine and Lake and Oak Ridge"),
            answer(prompt="two", text="Pine and Lake and Oak Ridge"),
            answer(engine="other", text="No recommendation."),
        ]
        report = run(self.dataset(spec, rows), 100_000)
        self.assertEqual(
            [
                (r["firm"], r["rank"], r["visibility_pct"], r["pooled_mention_pct"])
                for r in report["firms"]
            ],
            [("oak", 1, "50.00", "66.67"), ("pine", 1, "50.00", "66.67")],
        )
        self.assertEqual(report["engine_coverage"]["other"]["missing"], 1)

    def test_absent_engine_is_not_zero_visibility(self):
        spec = catalog()
        spec["engines"].append(dict(spec["engines"][0], id="other"))
        for rows, budget, pooled in [
            ([answer()], 100_000, "100.00"),
            ([answer()], 0, None),
            ([], 100_000, None),
        ]:
            with self.subTest(budget=budget, rows=len(rows)):
                report = run(self.dataset(spec, rows), budget)
                self.assertIsNone(report["firms"][0]["rank"])
                self.assertIsNone(report["firms"][0]["visibility_pct"])
                self.assertEqual(report["firms"][0]["pooled_mention_pct"], pooled)

    def test_half_up_rounding(self):
        self.assertEqual(percent(Fraction(1, 32)), "3.13")
        self.assertEqual(percent(Fraction(0)), "0.00")
