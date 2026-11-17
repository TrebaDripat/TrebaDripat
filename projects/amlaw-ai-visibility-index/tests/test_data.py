import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from visibility_index.data import DataError, citation, decimal_units, load_dataset


def catalog():
    return {
        "schema_version": 1,
        "label": "Test survey",
        "firms": [
            {
                "id": "pine",
                "name": "Pine & Lake",
                "aliases": [],
                "domains": ["pine.example"],
            }
        ],
        "engines": [
            {
                "id": "atlas",
                "input_usd_per_million": "0.150",
                "output_usd_per_million": "1",
            }
        ],
        "prompts": [{"id": "one", "text": "Who is mentioned?"}],
    }


def answer(**updates):
    return dict(
        {
            "engine": "atlas",
            "prompt": "one",
            "text": "Pine and Lake",
            "citations": [],
            "input_tokens": 10,
            "output_tokens": 4,
            "max_output_tokens": 20,
        },
        **updates,
    )


def write_data(path, spec, rows):
    (path / "catalog.json").write_text(json.dumps(spec), encoding="utf-8")
    (path / "answers.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


class DatasetTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)

    def test_exact_decimal_rates_and_budgets(self):
        self.assertEqual(decimal_units("0.150", 3), 150)
        self.assertEqual(decimal_units("0.000000001", 9), 1)
        for invalid in [-1, 0.5, "1e-3", "0.0001", "-1", "NaN", ""]:
            with self.subTest(invalid=invalid), self.assertRaises(DataError):
                decimal_units(invalid, 3)

    def test_normalized_citations_preserve_the_query(self):
        self.assertEqual(
            citation("HTTPS://BÜCHER.example.:443/news?a=1#quotes").url,
            "https://xn--bcher-kva.example/news?a=1",
        )
        self.assertEqual(
            citation("http://ALPHA.example:8080").url, "http://alpha.example:8080/"
        )
        for invalid in [
            "file:///notes",
            "https://user@pine.example",
            "//pine.example",
            "https://pine.example:bad",
            "https://a.example\\@pine.example",
            "https://",
            "https://a..example",
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(DataError):
                citation(invalid)

    def test_duplicate_key_pair_and_bad_references_fail_with_line_number(self):
        for row in [
            answer(),
            answer(prompt="two"),
            answer(engine="missing"),
            answer(input_tokens=True),
            answer(output_tokens=21),
            answer(output_tokens=-1),
            answer(citations=["file:///x"]),
        ]:
            with self.subTest(row=row):
                write_data(self.path, catalog(), [answer(), row])
                with self.assertRaisesRegex(DataError, "answers.jsonl:2"):
                    load_dataset(self.path)

    def test_ambiguous_catalog_entries_fail(self):
        for alternate in [
            {
                "id": "x",
                "name": "Pine and Lake",
                "aliases": [],
                "domains": ["other.example"],
            },
            {"id": "x", "name": "Other", "aliases": [], "domains": ["PINE.example."]},
        ]:
            spec = catalog()
            spec["firms"].append(alternate)
            write_data(self.path, spec, [])
            with self.assertRaisesRegex(DataError, "ambiguous"):
                load_dataset(self.path)

    def test_input_hashes_cover_the_original_bytes_and_handles_missing(self):
        write_data(self.path, catalog(), [])
        first = load_dataset(self.path)
        self.assertEqual(first.answers, ())
        with (self.path / "answers.jsonl").open("a", encoding="utf-8") as file:
            file.write("\n")
        self.assertNotEqual(
            first.sha256["answers.jsonl"],
            load_dataset(self.path).sha256["answers.jsonl"],
        )

    def test_duplicate_json_object_keys_are_rejected(self):
        write_data(self.path, catalog(), [])
        (self.path / "answers.jsonl").write_text(
            '{"engine":"a","engine":"b"}', encoding="utf-8"
        )
        with self.assertRaisesRegex(DataError, "duplicate JSON field"):
            load_dataset(self.path)
