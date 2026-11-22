# Offline fixture storyboard

Open [index.html](index.html) locally. Use Previous/Next, or Play storyboard for an eight-second
slide interval. Every frame visibly says **MOCKED FIXTURE — no live model**.

These are Chrome captures of the existing BeforeRun interface using the saved
`tests/fixtures/jobs/checked_result.json` fixture and intercepted application APIs. Selected UI
panels are framed at the top of each capture; the report content is unchanged. Chrome uses a
fresh temporary profile, disabled background networking, blocked external DNS and a policy
that forbids network connections. No source repository or provider is contacted.

The four frames show revision input, a partial report and compatibility comparison, inert source
evidence, and coverage/processing exclusions. The simulation, source identities, validation flags,
and fixture duration are synthetic. This recording establishes neither a live checked citation
nor latency, malware accuracy, or actual Kimi/Cerebras use. The live proof remains blocked.

Regenerate to a new output directory with the already installed browser and environment:

```sh
.venv/bin/python tests/fixtures/demo/record_demo.py --output /tmp/beforerun-demo-new
```

The generator refuses to overwrite existing frames. Review the captures before copying or sharing
them. [manifest.json](manifest.json) records hashes, render checks, visual review and the offline scope.
No publication or submission was performed.
