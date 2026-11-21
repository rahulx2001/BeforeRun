# Core behavior tests — write during the event

No investigation tests are present because the investigation itself is not implemented.

During the event, add meaningful checks for:

- rejected invalid repository URLs/refs and bounded source retrieval
- commit pinning when branches move, and missing comparison revisions
- a harmless repo revision, a fictional harmful update, and an apparent flag that is cleared
- command-specific setup relationships, including changed helpers behind unchanged hooks
- invalid or invented model citations
- differences between the selected source commits
- untrusted repository text that tries to alter investigator instructions
- bounded model loops, timeouts, and upstream errors
- visible gaps for partial retrieval and unresolved code

The [evaluation playbook](../docs/EVALUATION_AND_DEMO.md) specifies 27 proposed core
cases and the extra gate for conditional Python setup review. They remain specifications;
fixtures and tests must be written during the event.

Before kickoff, `make check` checks the scaffold's compilation and formatting only.

