# Release license review

Recorded 22 November 2026. This is a local release-preparation record; it does not
publish the repository. The project owner selected **Apache-2.0** in this task.

## Completed local checks

- Reviewed the project metadata, dependency lock, existing attribution draft, and
  installed Python distribution license metadata/text locations.
- Confirmed all 24 locked dependency distributions match installed versions and
  have license text available in the prepared environment. The 18 runtime and six
  development distributions are listed in [DEPENDENCY_NOTICES.md](DEPENDENCY_NOTICES.md).
- Identified additional notice requirements for bundled Ruff/Pygments/typing
  extensions, the MPL-2.0 certifi material, and Packaging's alternative licenses.
- Added the owner-selected canonical Apache-2.0 text as the root [LICENSE](../LICENSE),
  matching `pyproject.toml`'s license-file declaration, and added product [NOTICE](../NOTICE).
  The owner's reply was “Apache-2.0 (Recommended)” to the project-license question.

## Project authorship and inspiration

The existing implementation records attribute the BeforeRun product and local
source changes to this project, with evidence-first investigation inspired by
[Gatekeeper](https://github.com/lb2002/gatekeeper) by lb2002. The existing
[ATTRIBUTION_DRAFT.md](ATTRIBUTION_DRAFT.md) says the S09–S13 implementation did not
introduce Gatekeeper application modules. This statement describes that recorded
scope; it is not forensic proof that no earlier contributor copied or adapted
source, prompts, artwork, or fixtures.

Before public release, the project owner must confirm that they have permission
to license the included contributions and identify any earlier incorporated
third-party material. If Gatekeeper source was incorporated, retain its Apache-2.0
license, applicable copyright/NOTICE material, and modification notices for the
affected files. Inspiration attribution does not replace obligations for copied
material and does not imply upstream endorsement.

No upstream source checkout or network verification was performed for this local
metadata review. The Gatekeeper license expectation comes from the existing
project attribution record and must be checked against the actual reused revision
if code is incorporated.

## Remaining decisions and artifact checks

- [x] Project owner chooses the BeforeRun project license: Apache-2.0.
- [x] Add the chosen project license text, matching packaging metadata, and product notice.
- [ ] Confirm any prior third-party source, prompt, artwork, or fixture reuse and
  preserve that material's original obligations.
- [ ] Inspect the actual release artifact. If dependencies/tools are bundled, include
  their complete original licenses/notices, including transitive and vendored material.
- [ ] Verify service/provider terms separately if the artifact or hosted release uses
  OpenClaw/Cerebras; no account or terms attestation is supplied by metadata inspection.

The dependency inventory portion is complete for the current prepared environment.
The owner-selected project license is in place. Earlier contributor provenance and any
redistributed third-party material still require confirmation against the actual artifact.
Live-model/isolation gates and secret/demo
review are separate requirements in [RELEASE_GATES.md](RELEASE_GATES.md).
