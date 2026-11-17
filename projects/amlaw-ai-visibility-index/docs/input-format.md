# Replay input format

The CLI reads two UTF-8 files from the directory supplied to `--data`. The catalog describes the planned survey. The JSON Lines file supplies at most one answer per engine and prompt. File order sets the budget admission order. Blank lines are ignored.

## Catalog

The root of `catalog.json` contains `schema_version` (integer `1`), a display `label`, and the following nonempty lists. Identifiers use lowercase letters or digits with optional hyphen or underscore separators.

| Item | Required fields | Meaning |
| --- | --- | --- |
| Firm | `id`, `name`, `aliases`, `domains` | The display name is always a searchable alias. Additional aliases are strings. List one or more owned DNS hostnames. |
| Engine | `id`, `input_usd_per_million`, `output_usd_per_million` | Prices are nonnegative decimal strings, in USD per million tokens, with up to three fractional digits. |
| Prompt | `id`, `text` | A stable prompt identifier and its wording. All engines share the planned prompt set. |

Repeated IDs and aliases or hostnames assigned to multiple firms are rejected. Distinct firms may register a parent domain and one of its subdomains. The more specific registration owns links under that subdomain. [Example catalog](../examples/demo/catalog.json)

## Answers

Each nonblank line in `answers.jsonl` must contain one JSON object. This example uses the Atlas engine and privacy prompt from the demo catalog. It is expanded here for readability.

```json
{
  "engine": "atlas",
  "prompt": "privacy",
  "text": "Harbor & Finch publishes a privacy note.",
  "citations": ["https://insights.harbor-finch.example/privacy"],
  "input_tokens": 180,
  "output_tokens": 55,
  "max_output_tokens": 160
}
```

Token counts are nonnegative integers. Recorded output must fit the supplied ceiling. With the example Atlas prices of USD 1 and USD 3 per million input and output tokens respectively, this record reserves USD 0.000660 and spends USD 0.000345 if admitted. The budget accepts up to nine decimal places. Prices and token counts in the demo are synthetic.

An empty answer string is a supplied answer with zero prose mentions. Omit the entire record for a missing response. Keep supplied citations as absolute HTTP or HTTPS URLs. Host names are lowercased, international names use IDNA and default ports and URL fragments are removed. Paths, schemes, nondefault ports and query strings distinguish URLs. Duplicate URLs in one answer yield a single citation. Citing several pages from the same firm adds one to its answer-level citation count.

The matcher folds Unicode case and width, treats punctuation as token boundaries and expands an ampersand to “and.” It selects the longest matching alias at each position. Matches and owned citations are both deduplicated per firm and answer. A third-party URL containing a firm name in its host or path can still be recorded as an external citation.

## Reading the JSON audit

`coverage` and `engine_coverage` distinguish expected, supplied, analyzed, budget-skipped and missing answers. Each analyzed observation lists its input line number, engine, prompt, reservation, modeled cost, remaining budget, matched firms and canonical citation URLs. Budget-skipped rows retain the admission decision and balance. `firms` includes per-engine counts, the pooled mention rate, the equal-engine index and the count of answers with both a mention and an official citation.

Ranks use the unrounded index. Exact ties share a rank, and display percentages use two decimals. An undefined rate or rank is JSON `null` and an empty CSV cell. All money values are USD decimal strings. The output directory is published as a unit. Repeating an identical run succeeds, and a different result requires a different destination.
