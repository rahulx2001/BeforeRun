# Dependency license and notice inventory

Recorded 22 November 2026 from the prepared local Python environment, using
`importlib.metadata`, the pinned [requirements-dev.lock](../requirements-dev.lock),
and the installed distributions' license files. No dependency was downloaded,
installed, or upgraded for this inventory.

All 24 pinned distributions were present at their locked versions. The runtime
classification below follows the five direct application dependencies and their
active dependency markers on Python 3.12/macOS with no optional extras enabled.
There are 18 runtime distributions and six additional development distributions.
This inventory does not grant a publication license for BeforeRun itself.

## Pinned distributions

License file paths below are relative to the prepared environment's
`.venv/lib/python3.12/site-packages/`. They identify inspected upstream material;
they are not portable release links. Preserve the complete corresponding text
when redistributing a dependency, rather than substituting the short identifiers
or copyright summaries in this table.

| Distribution | Installed/locked version | Use | Metadata license | Installed license/notice text |
|---|---|---|---|---|
| annotated-doc | 0.0.6 | Runtime transitive | MIT | `annotated_doc-0.0.6.dist-info/licenses/LICENSE` |
| annotated-types | 0.8.0 | Runtime transitive | MIT | `annotated_types-0.8.0.dist-info/licenses/LICENSE` |
| anyio | 4.16.0 | Runtime transitive | MIT | `anyio-4.16.0.dist-info/licenses/LICENSE` |
| certifi | 2026.10.23 | Runtime transitive | MPL-2.0 | `certifi-2026.10.23.dist-info/licenses/LICENSE` |
| click | 8.5.1 | Runtime transitive | BSD-3-Clause | `click-8.5.1.dist-info/licenses/LICENSE.txt` |
| fastapi | 0.162.7 | Runtime direct | MIT | `fastapi-0.162.7.dist-info/licenses/LICENSE` |
| h11 | 0.16.0 | Runtime transitive | MIT | `h11-0.16.0.dist-info/licenses/LICENSE.txt` |
| httpcore | 1.0.9 | Runtime transitive | BSD-3-Clause | `httpcore-1.0.9.dist-info/licenses/LICENSE.md` |
| httpx | 0.28.1 | Runtime direct | BSD-3-Clause | `httpx-0.28.1.dist-info/licenses/LICENSE.md` |
| idna | 3.20 | Runtime transitive | BSD-3-Clause | `idna-3.20.dist-info/licenses/LICENSE.md` |
| iniconfig | 2.3.1 | Development transitive | MIT | `iniconfig-2.3.1.dist-info/licenses/LICENSE` |
| opentelemetry-api | 1.45.2 | Runtime transitive | Apache-2.0 | `opentelemetry_api-1.45.2.dist-info/licenses/LICENSE` |
| packaging | 26.3 | Development transitive | Apache-2.0 OR BSD-2-Clause | `packaging-26.3.dist-info/licenses/LICENSE`, `LICENSE.APACHE`, `LICENSE.BSD` |
| pluggy | 1.7.0 | Development transitive | MIT | `pluggy-1.7.0.dist-info/licenses/LICENSE` |
| pydantic | 2.14.3 | Runtime direct | MIT | `pydantic-2.14.3.dist-info/licenses/LICENSE` |
| pydantic_core | 2.50.4 | Runtime transitive | MIT | `pydantic_core-2.50.4.dist-info/licenses/LICENSE` |
| Pygments | 2.21.0 | Development transitive | BSD-2-Clause | `pygments-2.21.0.dist-info/licenses/LICENSE`, `AUTHORS` |
| pytest | 9.2.0 | Development direct | MIT | `pytest-9.2.0.dist-info/licenses/LICENSE` |
| python-dotenv | 1.2.4 | Runtime direct | BSD-3-Clause | `python_dotenv-1.2.4.dist-info/licenses/LICENSE` |
| ruff | 0.17.5 | Development direct | MIT; bundled notices also present | `ruff-0.17.5.dist-info/licenses/LICENSE` |
| starlette | 1.10.0 | Runtime transitive | BSD-3-Clause | `starlette-1.10.0.dist-info/licenses/LICENSE.md` |
| typing-inspection | 0.4.5 | Runtime transitive | MIT | `typing_inspection-0.4.5.dist-info/licenses/LICENSE` |
| typing_extensions | 4.16.0 | Runtime transitive | PSF-2.0; historical notices also present | `typing_extensions-4.16.0.dist-info/licenses/LICENSE` |
| uvicorn | 0.54.0 | Runtime direct | BSD-3-Clause | `uvicorn-0.54.0.dist-info/licenses/LICENSE.md` |

`License-Expression` was used when available. Otherwise the installed metadata's
`License` value/classifier was used and the installed license file was located.
HTTPX has an installed `LICENSE.md` even though this distribution's metadata did
not advertise a `License-File` field.

## Retention when distributing dependencies

- MIT/BSD packages: retain their complete copyright, conditions, permission text,
  and disclaimers. BSD name/endorsement restrictions remain applicable.
- OpenTelemetry API: retain its Apache-2.0 text and any notices present in the
  actual distributed artifact; preserve modifications/attribution as applicable.
- Packaging: its expression offers Apache-2.0 or BSD-2-Clause. Preserve the upstream
  `LICENSE`, `LICENSE.APACHE`, and `LICENSE.BSD` files in a bundled developer environment.
- Certifi: retain the MPL-2.0 license and the certificate bundle's applicable
  upstream/source notices. When distributing covered files or modifications, review
  source-availability obligations for that artifact. This does not establish that
  BeforeRun application source must use MPL-2.0.
- Pygments: preserve `AUTHORS` as well as `LICENSE`.
- Ruff: preserve the entire installed `LICENSE`, including its bundled third-party
  notices. Treating that file as only Ruff's short MIT notice would omit material.
- Typing extensions: preserve the entire installed PSF/historical license text;
  do not replace it with a one-line `PSF-2.0` label.

The current source tree uses Python dependencies by import and does not vendor
these installed distribution directories. If a future wheel, executable, container,
or demo bundle includes their code, include the applicable original license/notice
files with that artifact and verify the artifact contents. This inventory alone is
not a bundled license archive or a completed distribution review.

## Tooling outside the pinned application dependencies

The local environment also contains pip 26.2.2 (MIT plus vendored third-party
licenses). It is an environment tool, not one of the 24 locked application/dev
distributions. If redistributing the environment, retain all pip vendored notices.
The build configuration references `setuptools>=68` and `wheel`; their eventual
build-environment versions/notices must be inventoried if included in a distribution.

OpenClaw Gateway, Node, Python, and Chrome are operator-supplied tools, not files
included by this Python source dependency inventory. Their own distribution
licenses, service terms, provider terms, and browser permissions require separate
review if those tools are bundled. No upstream Gateway/provider account terms were
retrieved or attested here.

Gatekeeper inspiration and any potential prior source reuse are covered in
[ATTRIBUTION_DRAFT.md](ATTRIBUTION_DRAFT.md) and
[RELEASE_LICENSE_REVIEW.md](RELEASE_LICENSE_REVIEW.md).
