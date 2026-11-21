# Package manager roadmap

> **Background ecosystem roadmap.** Follow
> [MASTER_BUILD_PLAN.md](MASTER_BUILD_PLAN.md), especially its artifact/audit/guard
> milestones in section 23. Repository setup analysis and registry-artifact coverage
> remain separate; older examples here do not enable untested package managers.

BeforeRun's selected first workflow is **public GitHub repository review**, confirmed
on **15 November 2026**. Registry package inputs follow that workflow. This roadmap was
recorded on 14 November and updated for that scope decision; repository and package
investigation remain unimplemented in the pre-event scaffold under
[the timing rule](HACKATHON_RULES.md).

Package/dependency investigation remains part of the intended Gatekeeper-inspired
product. GitHub review adds another input and is prioritized for the first event
milestone. See [the scope clarification](PRODUCT_SCOPE.md).

The user's reference to “ux” is provisionally interpreted as **uv**, the Python tool.

The [research brief](RESEARCH_BRIEF.md) and [evaluation plan](EVALUATION_AND_DEMO.md)
require Node for the event demonstration and gate Python setup support on dedicated
validation. Registry artifact adapters remain later milestones.

## Recommended order

| Stage | Tools | Ecosystem | First useful coverage |
|---|---|---|---|
| 0: hackathon core | GitHub repository URL; selected npm/pip command context | Public Node source; Python conditional | Pin a commit, inspect selected setup/build paths, optionally compare a baseline, and show checked evidence. Registry artifacts and dependencies are separate scope. |
| 1: next input | npm; packages also used by Yarn and pnpm | npm registry | Inspect one exact public package release, compare versions, and show checked evidence. Yarn/pnpm lockfiles and command guards are separate work. |
| 2: next ecosystem | pip and uv | Python / PyPI | Inspect a selected wheel, then source distributions; distinguish build, interpreter-startup, and import behavior. |
| 3 | Homebrew (`brew`) | Formulae and casks | Review official recipe/metadata revisions, installation steps, URLs, and advertised checksums; show limitations around binary payloads. |
| 4 | Cargo | Rust / crates.io | Review crate source, `Cargo.toml`, and build scripts; extend analysis for procedural macros and native build dependencies. |
| Later candidates | Composer, NuGet, Maven/Gradle, Go tools, Conda | Other development ecosystems | Define artifact retrieval, execution behavior, and evidence checks for each before committing to support. |
| Later candidates | apt, dnf | Linux system packages | Review repository/package provenance and maintainer scripts, with platform-specific archive and installation handling. |

These stages are priorities rather than promises about how many ecosystems fit one
weekend. Each needs implementation and verification. Add npm registry input after
repository review works, then PyPI artifact inspection. Reading Python setup files in
a GitHub snapshot does not establish PyPI artifact or pip/uv command-guard support.
Keep registry adapters and the remaining candidates outside the current 24-hour schedule.

## What support means

Track three separate capabilities for each tool:

1. **Package investigation:** analyze an exact release and selected artifact as data.
2. **Project audit:** understand the project's actual package sources, locked versions,
   dependency paths, platform targets, and configuration.
3. **Install guard:** intercept supported commands and check the artifacts those commands
   will use before any relevant package code can execute.

Implementing package investigation does not establish the other two capabilities.
pip and uv share Python artifacts, but configuration, resolution, lockfiles, and guard
commands differ. npm, Yarn, and pnpm likewise share registry packages while retaining
different project and command behavior. Publish coverage for each capability explicitly.

## Shared investigation engine

Reuse the repository workflow's interface/UI and Kimi read/search investigation engine.
Each registry ecosystem adapter supplies:

- Exact name/version, origin, artifact URL/digest, and relevant platform/interpreter scope.
- Bounded artifact retrieval and parsing, without installing or running package code.
- Manifest, source files, numbered excerpts, and ecosystem-specific execution entry points.
- A comparison baseline with matching scope, plus a record of unread or unsupported content.
- Deterministic reference checks and supported execution-path checks for that ecosystem.

Use the same readable finding/evidence/unknown result format across ecosystems. Display
the exact artifact inspected; one inspected wheel or bottle does not cover every artifact
published for that version. Kimi can interpret evidence, while code checks references,
hashes, budgets, and supported relationships.

## Python: pip and uv

Start with a public PyPI name, exact version, and selected artifact. Obtain artifact URLs
and digests from the registry and retrieve the artifact directly. Do not invoke pip or uv
to build or generate source metadata inside the scanner: these operations can invoke
package-controlled build backends.

The planned adapter should:

- Inspect wheel ZIP entries, distribution metadata, packaged scripts, Python files,
  and interpreter startup hooks such as `.pth` and version-supported `.start` files.
- Inspect source-distribution manifests, `pyproject.toml`, `setup.py` where present,
  and identified build backends/hooks as data. An absent `setup.py` does not establish
  that a source build cannot execute code.
- Label compiled extensions and unresolved build/import paths as analysis gaps.
- Show the Python/platform target and selected wheel/source archive. Check the archive
  digest against registry metadata; a matching digest establishes identity, not benignness.
- Add `requirements.txt`, `pyproject.toml`, and `uv.lock` project handling as a later
  capability. Respect manager-specific indexes and configuration; unresolved requirements
  must not silently be treated as exact public PyPI versions.

Completion requires Python-specific harmless and fictional risky fixtures, meaningful
artifact/reference checks, and visible uncertainty for native code and unsupported paths.

## Homebrew

Begin with official formula/cask metadata and the corresponding recipe revision. Read
these as data; the scanner must not evaluate recipe Ruby or execute installers.

Review dependencies, download locations, expected checksums, source-install behavior,
declared post-install steps, and cask installation artifacts/steps. Current Homebrew
documentation describes declarative post-install and cask preparation steps; legacy or
third-party recipe behavior needs explicit handling. Applying npm hook rules to these
recipes would not establish their execution behavior.

A formula can install a prebuilt bottle instead of building from source. A cask can
install an application or vendor installer. A recipe review and matching download
checksum do not establish the behavior of those binary contents. Identify the selected
platform/artifact and report that gap. Extend binary, installer, custom-tap, and command
coverage in separate stages after recipe review works.

## Interface plan

Begin with the GitHub repository form. Add a source selector such as
**GitHub / npm / PyPI / Homebrew** when those investigations are operational.
Manager-specific project or install modes can request npm/pnpm/Yarn or
pip/uv context separately. Show planned ecosystems as planned in documentation; claims
of supported investigation must match a functioning adapter and its stated scope.

## Documentation consulted

- [pip build-system interface](https://pip.pypa.io/en/stable/reference/build-system/)
  and [pip download](https://pip.pypa.io/en/stable/cli/pip_download/).
- [uv compatibility with pip](https://docs.astral.sh/uv/pip/compatibility/).
- [PyPI JSON API](https://docs.pypi.org/api/json/).
- [Wheel format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)
  and [Python site/startup configuration](https://docs.python.org/3/library/site.html).
- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
  and [Cask Cookbook](https://docs.brew.sh/Cask-Cookbook).
- [Cargo build scripts](https://doc.rust-lang.org/cargo/reference/build-scripts.html).
