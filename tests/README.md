# BeforeRun tests

Run the offline suite with:

```sh
.venv/bin/python -m pytest -m 'not live' tests
```

The current tests cover typed contracts, shared budgets, bounded GitHub/evidence behavior,
pinned comparison, owned jobs, cancellation/idempotency/export, and static UI/API safety.
They use mocked HTTP and checked-report fixtures by default and must not make model calls.

Fixtures are inert and annotated. The Node 20→22 case checks original-side comparison only;
the checked job JSON contains simulated text and zero model attempts. Neither establishes
malware detection, model quality, complete source coverage, or browser/live integration.

A `live` marker is reserved for explicitly authorized integration tests. Opting in must fail
honestly when the required route or tool contract is unavailable; live access must never be
silently skipped or replaced with a direct provider/fallback model.
