# AmLaw AI Visibility Index

A Python tool for auditing how often law firms appear in recorded model answers. It counts firm mentions, attributes citation URLs to registered firm domains and shows which answers fit a per-run budget. Every decision links back to a line in the input file.

This portfolio implementation uses fictional firms, three synthetic engine labels and example prices. The original survey data is unavailable. You can inspect the [full report](reports/demo/index.md), [budget-limited report](reports/budgeted/index.md) and [labeled input](examples/demo/README.md) directly on GitHub.

## Run the demo

From this project directory, use Python 3.11 or newer. The replay runs offline using the standard library.

```sh
python -m visibility_index --data examples/demo --budget-usd 0.025 --out build/full
python -m visibility_index --data examples/demo --budget-usd 0.004 --out build/limited
python -m unittest discover -s tests -v
```

Open `build/full/index.md` for the rankings, `firms.csv` for the table, or `report.json` for per-answer mentions, citations and budget decisions. Each run records SHA-256 hashes of its two input files. Repeating a run with identical inputs and settings reproduces the same files byte for byte.

## What changes when the budget is smaller?

The fixture covers six prompts and three engines. Seventeen answers were supplied, with the incident-response answer from one engine deliberately missing.

| Run | Limit (USD) | Modeled spend (USD) | Analyzed | Skipped for budget | Missing |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full | 0.025 | 0.007461 | 17 | 0 | 1 |
| Limited | 0.004 | 0.003677 | 10 | 7 | 1 |

In the full replay, Morrow Vale Legal and Harbor & Finch each appeared in seven answers. Their visibility scores were 42.22% and 41.11%. Each engine has equal weight, and Morrow Vale appeared more often on the engine that supplied five answers. With the smaller budget the two firms tied at 41.67%. The scores describe the admitted sample. [Per-engine counts and admission decisions](reports/demo/report.json)

The full sample contained 25 citation URLs after deduplication within answers. Seventeen pointed to a registered firm domain or one of its subdomains. A link can count even when the prose never mentions the firm. Third-party sources remain visible in the audit with a null owner. [Expected attributions for all 17 answers](examples/demo/labels.json)

## Method

- **Mentions.** Normalize Unicode and case, match whole alias tokens and count each firm once per answer. A visible Markdown link label can mention a firm. URL text is excluded from name matching.
- **Citations.** Match the most specific registered DNS suffix on a label boundary. Count an answer as citing a firm when at least one supplied URL belongs to that firm. The audit records attribution by domain. Evaluating whether a page supports a claim requires reviewing its contents.
- **Visibility.** Compute the percentage of analyzed answers mentioning a firm for each engine, then take the arithmetic mean. The report also includes the pooled rate. Missing and budget-skipped pairs are excluded from both denominators. An engine with no analyzed answers leaves the balanced index undefined.
- **Budget.** Visit recorded answers in file order. Reserve the cost of the input and maximum possible output. If it fits, charge the modeled cost of the recorded usage and release the balance. If it does not fit, keep the budget available for later rows. Costs are calculated in integer nanodollars.

To use your own exports, prepare a catalog and normalized answers file. The format documents field types, attribution rules and a worked cost example. [Input format](docs/input-format.md) · [CI runs](https://github.com/TrebaDripat/TrebaDripat/actions/workflows/amlaw-visibility.yml)
