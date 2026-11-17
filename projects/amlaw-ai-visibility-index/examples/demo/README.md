# Synthetic survey

Four fictional law firms, six prompts and three fictional engine labels form an 18-cell survey. The 17 answer texts, links, usage figures and example prices were written for this demonstration. The intentionally missing cell is the `cobalt` answer to `breach`.

The catalog defines aliases, owned hosts and example prices. The answer file sets admission order. The labels file records the expected mentioned firms and owners of cited domains for each supplied answer. It is read by the tests. [Catalog](catalog.json) · [Answers](answers.jsonl) · [Expected labels](labels.json)

The examples include a firm cited without a prose mention, a firm mentioned without an official link, a third-party hostname containing a firm hostname, a Unicode dash, equivalent URL fragments and a Markdown link label. Every hostname uses the reserved `.example` suffix.
