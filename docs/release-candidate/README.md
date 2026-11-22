# Local release candidate

This directory contains review material, not a published or enabled scanner.

`APACHE-2.0.txt` is the selected BeforeRun license text, copied verbatim from the canonical
Apache-2.0 text available in the installed Packaging distribution. It is not that
distribution's application source or a copy of its author-specific copyright notice.
The project owner selected **Apache-2.0** in this task. The same text is now the root
`LICENSE`, and `pyproject.toml` declares that file. `NOTICE` records product attribution;
the dependency inventory records separately licensed packages.

The publication candidate contains application source, inert development tests, pinned
dependency declarations, selected product/release documents, and the explicitly mocked
demo storyboard. It excludes personal assistant state, `.env`, provider logs, managed
Gateway state, installed environments, and historical planning/design artifacts.
Dependencies and operator tools are referenced, not bundled.

The release gates still require successful authorized live isolation, native evidence,
checked citations, upstream identity, usage/cost measurements, and final release sign-off.
The local snapshot and offline demo cannot establish those results.

The local [CHECKPOINT.json](CHECKPOINT.json) and [MANIFEST.json](MANIFEST.json) identify the
parentless offline candidate and its checked archive. The exact committed archive passed
316 offline tests and one real-Chrome test with mocked APIs. The original Git branch/index
were preserved, and no remote publication occurred. These audit attachments are separate
from the frozen self-hashed product file list.

That checkpoint predates the subsequently approved Baseten configuration/disclosure change.
Its original files/checks remain historical. Export a fresh candidate and complete the new
provider's live gates before treating the current working tree as an enabled release.
