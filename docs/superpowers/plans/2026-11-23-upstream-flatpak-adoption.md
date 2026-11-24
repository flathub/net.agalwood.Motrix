# Upstream Motrix Flatpak Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship upstream Motrix v2.4.5 through the existing Flathub identity with reproducible offline inputs and a safe source-sync workflow.

**Architecture:** Adapt the exact upstream recipe, patch only retained-identity contracts, and install metadata from the application checkout. Copy upstream's committed dependency lists rather than regenerate them; treat recipe drift as a maintainer-review gate. The independently deliverable host-companion contribution is in the [companion plan](2026-11-23-flatpak-companion-compatibility.md) and is not a downstream release prerequisite.

**Tech Stack:** Flatpak/Flathub, Freedesktop/Electron BaseApp 25.08, Node 24, pnpm 12.21.0, Rust/Cargo, Python 3/PyYAML, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-22-upstream-flatpak-adoption-design.md`

## Global Constraints

- Retain `net.agalwood.Motrix`, `net.agalwood.Motrix.yml`, module name `motrix`, and `~/.var/app/net.agalwood.Motrix/`.
- Build `v2.4.5`, peeled commit `6099f17c585e5accb45972283a638229f24ab64b`, from `https://github.com/agalwood/Motrix.git`; not annotated tag object `0edbc7f9a7a01c097a9c4f8ffeeac9cf9b5eba5b`.
- Runtime and Electron BaseApp remain Freedesktop `25.08`; target `x86_64` and `aarch64`, not i386/armv7.
- Preserve Node `24`, pnpm `12.21.0`, Electron `45.3.3` headers, upstream's pinned architecture-specific Rust toolchains, and aria2 `v1.37.0-motrix.25` with c-ares/libssh2 dependencies.
- Copy `flatpak/generated-sources.json` and `flatpak/cargo-sources.json` from the immutable application commit. No downstream generator toolchain.
- Preserve upstream's signed builtin-plugin verification, staging order, wrappers, private broker, Downloads-plus-portals permissions, and exact-ID/path/caller/framing/nonce security checks.
- Keep `Exec=start-motrix %U` and upstream's current WM class unless runtime testing establishes a required adjustment.
- No spoofing `FLATPAK_ID`, host escape, broader D-Bus access, host-companion payload/browser manifests, or host installation from inside the sandbox.
- No downstream migration wrapper, forced legacy import, profile relocation/deletion, database reset, or independent engine/plugin/toolchain updates.
- Do not claim seamless v1 migration or browser integration with the current unmodified upstream companion.
- The spec still says “proposed; awaiting user approval.” Planning is authorized; implementation/publication requires explicit design/plan approval. No commits or branches without explicit authorization; commit checkpoints below are conditional.

## Review Focus

1. A differently cased/unknown/missing Flatpak ID must be rejected, not accidentally accepted by an identity rewrite — Task 1 negative identity tests.
2. A partial source download, malformed JSON, or mismatched annotated tag must leave both local lists and the PR branch untouched — Task 3 failure-injection tests.
3. Reordered modules, coupled upstream recipe changes, or a concurrently advanced PR must never cause stale pins or overwrite new work — Task 3 selection, drift, and concurrency tests.
4. A real v1 profile with non-Downloads destinations and preexisting overrides must remain recoverable; discovery/invitation is not proof that all preferences or progress converted — Task 4 disposable-profile matrix.
5. Two installed Motrix IDs and the currently released companion must not produce a false browser-integration success or silently route users to this package — Task 4 interim-integration checks.

---

## File and responsibility map

Paths below are relative to this packaging repository unless explicitly marked upstream.

| Action                            | File                                                                               | Responsibility                                                                                                               |
| --------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Create                            | `patches/retain-flathub-id.patch`                                                  | Small upstream source/test diff for this build's desktop and sandbox identity                                                |
| Modify                            | `net.agalwood.Motrix.yml`                                                          | Adapted upstream build, stable application checker, local includes, patch, checkout metadata installation                    |
| Replace/Create                    | `generated-sources.json`, `cargo-sources.json`                                     | Byte-for-byte upstream offline input lists                                                                                   |
| Delete after references disappear | `net.agalwood.Motrix.desktop`, `net.agalwood.Motrix.metainfo.xml`                  | Eliminate independently maintained metadata                                                                                  |
| Delete/Create                     | `.github/workflows/auto-update.yml`, `.github/workflows/sync-upstream-sources.yml` | Replace push-triggered Yarn generation with trusted-PR/manual sync                                                           |
| Create                            | `.github/scripts/sync_upstream_sources.py`                                         | Trusted orchestration, deterministic manifest adaptation, immutable retrieval, consistency checks, allowlisted API writeback |
| Create                            | `docs/migration-v2.md`                                                             | User migration/permission/interim-companion notes and maintainer update/validation runbook                                   |

Keep validation-only scripts and fixtures under already ignored `.flatpak-builder/validation/`; do not commit a packaging test suite or copied upstream source tree. Upstream regression tests belong in the identity patch. Do not touch unrelated `shared-modules` assets.

## Task 1: Produce the narrow retained-identity patch

**Files:** Create `patches/retain-flathub-id.patch`. In an ignored checkout at `.flatpak-builder/validation/upstream/`, patch upstream `src/main/bridge/flatpak-environment.ts`, `src/main/bridge/flatpak-environment.test.ts`, `src/shared/constants.ts`, `packages/native-host/src/lib.rs`, and identity-specific fixtures in `packages/native-host/src/user_data.rs` and `packages/native-host/src/flatpak_companion/tests.rs` as needed. Audit before changing any additional file.

**Interfaces:** Consumes the pinned application commit. Produces a patch applied after the application git source and before compilation; in this build, `MOTRIX_FLATPAK_ID` and desktop `APP_ID` are exactly `net.agalwood.Motrix`. No companion API changes from the separate plan belong here.

- [ ] **Step 1: Add failing upstream regression assertions in the ignored checkout.** Extend `flatpak-environment.test.ts` to assert the exported constant equals the literal `net.agalwood.Motrix`, packaged Linux with that ID returns true, and `app.motrix.native`, `net.agalwood.motrix`, missing ID, development mode, and non-Linux return false. Extend existing Rust identity tests to accept only the retained ID with absolute XDG config paths and reject upstream/unknown IDs and relative/missing config paths. Keep framing/caller/nonce negative tests unchanged.
- [ ] **Step 2: Run the focused tests and record the expected identity failures.** From the ignored upstream checkout, use its locked dependencies and run `pnpm --config.verify-deps-before-run=false exec vitest run src/main/bridge/flatpak-environment.test.ts` and `cargo test --manifest-path packages/native-host/Cargo.toml --locked user_data`. Expected: the new retained-ID assertions fail, not dependency/setup failures. If tooling is blocked, record that and do not claim a red test was observed.
- [ ] **Step 3: Change the three production identity constants and affected identity fixtures.** Audit `APP_ID` callers and production `app.motrix.native` references, including Electron packaging identity, before patching. Align desktop identity where required; leave `app.motrix.bridge`, extension IDs, service/protocol names and security logic intact. Update the companion process-runtime fixture's expected fixed ID because this shared constant changes the transient host build too; this does not deliver a new host companion.
- [ ] **Step 4: Run focused and full native-host tests, then export only the source/test diff as the patch.** Run the Vitest command above and `cargo test --manifest-path packages/native-host/Cargo.toml --locked`. Expected: pass, including broker, caller and unsafe-path cases. Verify `git apply --check` on a separate pristine checkout of the pinned commit and inspect the patch for unrelated replacements. Upstream packaging-contract tests hardcoded to its own ID are not downstream acceptance tests; do not weaken them merely to make the adaptation appear unchanged.
- [ ] **Step 5: Review checkpoint.** Review patch hunks and test evidence. Only if commits have been authorized: `git add patches/retain-flathub-id.patch` then `GIT_EDITOR=true git commit -m "fix: preserve the Flathub desktop and broker identity"`.

## Task 2: Adopt the complete offline recipe and checkout-owned metadata

**Files:** Modify `net.agalwood.Motrix.yml:1-146`; replace `generated-sources.json`; create `cargo-sources.json`; delete the two downstream metadata files once unused. Reuse Task 1's patch.

**Interfaces:** Consumes the patch and upstream `flatpak/app.motrix.native.yml` plus both source lists at the pinned commit. Produces a fully resolved manifest whose source selection is the unique `motrix` module's git source with URL `https://github.com/agalwood/Motrix.git`. Task 3 must reproduce the adaptation described below structurally, not normalize away arbitrary differences.

- [ ] **Step 1: Write an ignored structural acceptance check.** Create `.flatpak-builder/validation/test_packaging.py` using `unittest`, PyYAML and XML parsing. Assert the pinned tag/commit; ordered modules `c-ares`, `libssh2`, `aria2`, `motrix`; Node 24; both local includes; patch source; x86_64/aarch64 mappings without old architecture mappings; Downloads but no home permission; no independent aria2 checker; and JSON lists byte-equal to upstream. Assert metadata install commands read checkout `flatpak/` files, not deleted local sources. Keep the expected upstream recipe in the ignored validation directory, not a third maintained manifest.
- [ ] **Step 2: Run `python3 .flatpak-builder/validation/test_packaging.py`.** Expected: fail against the current Yarn/v1 manifest and missing Cargo list.
- [ ] **Step 3: Replace the recipe and copy both lists without reserialization.** Start from upstream's exact manifest; retain every module, digest, environment value, offline command, source-built-engine feature assertion, Rust archive, signed plugin input, broker installation, and wrapper behavior. Apply only these adaptations:
  - Set root app ID to `net.agalwood.Motrix`; retain `motrix` module name and all upstream build paths.
  - Replace the placeholder application git source with the public URL, `v2.4.5` and peeled commit. Set checker to `type: git`, `tag-pattern: '^v([0-9]+\.[0-9]+\.[0-9]+)$'`. Omit `is-main-source` to avoid metainfo updates against a nonexistent downstream file.
  - Remove aria2's independent `x-checker-data`; its pinned source still tracks the application contract.
  - Insert Task 1's patch source immediately after the application git source. Keep both JSON includes local at repository root.
  - Remove only the two upstream metadata `type: file` sources: those assets already exist in the checkout. Replace their install commands to read `flatpak/app.motrix.native.desktop` and `flatpak/app.motrix.native.metainfo.xml` and write under the retained filenames.
  - After installation, replace only desktop `Icon=app.motrix.native`, XML component `<id>app.motrix.native</id>`, and the desktop-id launchable with the retained values. Guard expected input matches so upstream format drift fails rather than silently producing wrong identity. Preserve all other metadata, `Exec`, WM class and upstream icon installation.
  - Do not add a new locale/wrapper/permission policy beyond the adopted upstream contract in this migration.
- [ ] **Step 4: Remove unused downstream metadata files.** Verify no manifest references remain before deletion; leave unrelated files alone.
- [ ] **Step 5: Run structural and tool validation.** Run the structural check, `flatpak-builder --show-manifest net.agalwood.Motrix.yml`, `flatpak run org.flathub.flatpak-external-data-checker --lint net.agalwood.Motrix.yml`, and `flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest net.agalwood.Motrix.yml`. Expected: all exit zero. Produce staged metadata with the exact manifest transformations and run `desktop-file-validate` and `appstreamcli validate --no-net` on the retained filenames; assert icon, component and launchable IDs, preserved `%U` and unchanged release history. Missing tools are blockers to record, not passing results.
- [ ] **Step 6: Review checkpoint.** Diff the adapted recipe against upstream and inspect the small allowlisted delta. If authorized, commit only this task's manifest, lists and metadata removals with message `build: adopt the upstream Motrix v2 offline recipe`.

## Task 3: Replace downstream regeneration with trusted immutable source synchronization

**Files:** Delete `.github/workflows/auto-update.yml`; create `.github/workflows/sync-upstream-sources.yml` and `.github/scripts/sync_upstream_sources.py`; document updater operation in `docs/migration-v2.md`.

**Interfaces:** Python script CLI: `python3 .github/scripts/sync_upstream_sources.py --repository OWNER/REPO --pr NUMBER [--reviewed-recipe-sha256 HEX] [--write]`; token only from `GH_TOKEN`. Default is check-only. Exit 0 for a consistent/no-op or successful sync; nonzero with an actionable error for retrieval, identity, recipe or concurrency failure. Produce a Markdown recipe diff in the Actions step summary on drift. No arbitrary URL, branch-name or executable input.

Define these internal seams for offline fixture tests: `application_source(manifest: dict) -> dict`, `adapt_manifest(upstream: dict, source: dict) -> dict`, and `validate_source_list(payload: bytes) -> list`. `adapt_manifest` is exactly Task 2's transformations and rejects unexpected source/metadata-command shapes. Networking and writeback stay in `main() -> int`; use mock HTTP responses, never a live write token, for local tests.

- [ ] **Step 1: Write ignored failing tests in `.flatpak-builder/validation/test_sync_upstream_sources.py`.** Assert these named cases using temporary directories/mock HTTP and the Task 2 recipe fixture:
  - `test_selects_application_by_name_and_url`: module reordering still finds the right source; duplicate/missing matches fail.
  - `test_adaptation_matches_checked_in_manifest`: structural equality after substituting the selected source, with no ignored build/pin/security fields.
  - `test_validates_stable_tag_and_peeled_commit`: accept v2.4.5 at the peeled SHA; reject prereleases, tag objects as commits, mismatches, malformed SHA and shell metacharacters.
  - `test_failed_pair_fetch_writes_nothing`: 404/timeout/truncated JSON/empty list/wrong top-level type in either download means neither destination or PR ref is changed. Test successful byte-for-byte copying without executing list contents.
  - `test_recipe_drift_requires_explicit_digest_and_consistent_adaptation`: changed pins, toolchains, plugins or commands fail and report a diff; even a review digest cannot bless a local manifest that differs from `adapt_manifest(new_recipe, source)`.
  - `test_noop_and_concurrent_update`: identical lists create no commit; an advanced PR head or closed/fork PR causes no write and a retryable error.
- [ ] **Step 2: Run `python3 .flatpak-builder/validation/test_sync_upstream_sources.py`.** Expected: fail because the helper/interfaces do not exist.
- [ ] **Step 3: Implement the helper.** Parse YAML safely; require HTTPS GitHub's fixed Motrix repository, `vN.N.N` and 40 lowercase hex commit. Resolve tag peeling via GitHub's API and compare to the manifest commit. Retrieve both lists and old/new recipes by immutable commits, with request timeouts and bounded responses; validate both before any write. Compare the candidate manifest structurally with `adapt_manifest(new_recipe, source)`.

  Report old-to-new upstream recipe drift and fail by default, even if lists copy cleanly. A maintainer may acknowledge an exact new recipe SHA256 only via manual dispatch, after reviewing the diff and updating the PR's local adaptation. Require this digest to equal the retrieved bytes; it never bypasses structural consistency. For initial v1-to-v2 adoption, handle the old commit's missing `flatpak/` recipe as a review-required bootstrap, not an empty successful comparison.

  For `--write`, create a single commit containing only the two generated lists via GitHub's Git data API, parented to the validated PR head. Re-fetch PR state/head immediately before a non-forced ref update; reject changed heads. Never use a shell to interpolate inputs, never run downloaded code, and never commit manifest/patch/workflow/metainfo changes. No-op if both blobs already match.

- [ ] **Step 4: Implement the workflow trust boundary.** Use `pull_request_target` for `opened`, `synchronize`, `reopened`, `ready_for_review` with a manifest path filter, and `workflow_dispatch` taking a numeric PR number and optional reviewed recipe SHA256. Load script/workflow only from the event's trusted base revision (default branch for manual runs); never execute the PR checkout. Require an open same-repository PR targeting the default branch and an allowlisted update-bot login or repository collaborator with write/maintain/admin permission, verified through the API. Do not rely on PR labels as authorization.

  Set workflow permissions to `contents: read`; scope `contents: write` and `pull-requests: read` to the sync job. Use pinned checkout/setup-python actions, `persist-credentials: false`, job timeout and per-PR concurrency. Install a reviewed exact PyYAML version in the trusted environment. Pass event data through environment variables/validated CLI arguments, never direct expression interpolation into shell source. Pass `GITHUB_TOKEN` as `GH_TOKEN` only to the trusted helper. Manual review digest input is accepted only for `workflow_dispatch`, never from PR content.

- [ ] **Step 5: Run fixture tests and a disposable trusted-PR exercise.** Expected: all fixture tests pass. Check workflow syntax with `actionlint .github/workflows/sync-upstream-sources.yml`. On an explicitly authorized disposable same-repository PR, exercise no-op, successful two-list sync, failed retrieval, tag mismatch, unreviewed drift, acknowledged-but-inconsistent drift, and stale-head refusal; forks must skip without acquiring a write path. Verify a successful bot commit contains only the two source lists. Do not test writes against a real release PR.
- [ ] **Step 6: Document and verify CI handoff.** State that `GITHUB_TOKEN` pushes do not reliably trigger downstream workflows. After sync, a maintainer must explicitly request Flathub validation of the resulting head SHA using the repository's supported buildbot/retest mechanism and verify checks attach to that SHA before merge; record the actual mechanism from this repository's CI rather than invent a bot command. No new App/PAT secret is required by this design. Record manual recipe review/digest dispatch procedure and bootstrap behavior.
- [ ] **Step 7: Review checkpoint.** Review trust boundary and failure fixtures. If authorized, commit workflow/helper/docs and removal of the old workflow with message `ci: synchronize reviewed upstream Flatpak source lists`.

## Task 4: Prove both-architecture payloads and real-profile behavior; finish migration notes

**Files:** Finish `docs/migration-v2.md`. Only add another patch hunk if verified legacy-path or runtime evidence requires the narrow compatibility adjustment allowed by the spec.

**Interfaces:** Consumes Tasks 1–3's package and sync helper. Produces a release acceptance record with exact tested SHAs, architecture results, UI/profile results, and explicit untested blockers. Browser integration remains unavailable until a compatible companion is released and explicitly installed.

- [ ] **Step 1: Establish recoverable fixtures before building/installing.** Obtain a consented disposable copy of an actual v1 Flatpak profile, never operate on the only live profile. Preserve v1 application/settings/engine databases, source JSON files and download files; verify a backup can be restored in a separate test account/VM. Record old schema versions, profile layout and non-Downloads destinations without committing personal data. Fresh profiles alone are not adequate migration evidence.
- [ ] **Step 2: Build offline on native x86_64 and aarch64 workers.** On each worker run `flatpak-builder --arch=x86_64 --download-only build-x86_64 net.agalwood.Motrix.yml` then `flatpak-builder --arch=x86_64 --disable-download --force-clean build-x86_64 net.agalwood.Motrix.yml`, using the corresponding `aarch64`/`build-aarch64` values on ARM. Retain logs proving network-isolated build phases, correct headers/toolchains/signed artifacts, source-built aria2 feature checks, native broker/finalize helper and no installed browser-facing host/manifests. Use Flathub CI if local sandbox/tooling cannot run; do not weaken confinement to get a green result.
- [ ] **Step 3: Validate installed exports and probe the broker.** Install each test build in a disposable environment. Validate installed desktop/metainfo with the validators from Task 2, the retained icon/IDs, and manifest/build lint. Confirm aria2 `1.37.0-motrix.25` has upstream's asserted features and WebSocket binary marker, private broker and finalize helper exist, transient build staging is cleaned, and wrapper retains portal/bridge-data/TMPDIR behavior.

  With Motrix stopped, send the exact upstream framed probe with only the app ID changed:

  ```sh
  printf 'MXBR\001\000\000\000\025\000\000\000%s' '{"operation":"probe"}' | flatpak run --command=motrix-native-host-broker net.agalwood.Motrix | od -An -tx1 -v
  ```

  Expected bytes, ignoring whitespace: `4d584252010000001e0000007b226572726f72223a226d6f747269782d6e6f742d72756e6e696e67227d` (`motrix-not-running`), not `invalid Motrix Flatpak environment`. Keep wrong-ID and malformed-frame rejection tests from Task 1.

- [ ] **Step 4: Run the interactive acceptance matrix.** In the disposable desktop environment, verify ordinary download/pause/resume, destination selection outside Downloads through the portal, secondary-launch handoff, and Wayland and X11 startup. Check both fresh default permissions and a profile with preexisting user overrides: defaults no longer grant home, overrides are not silently deleted. With the copied v1 profile, verify discovery under upstream's actual `$XDG_CONFIG_HOME/Motrix` / `~/.config/motrix` search behavior and consent/onboarding conditions, one-time Migration Assistant invitation, explicit confirmed task import, imported paused records and no transfer before activation. Verify supported internal settings/application/engine DB upgrades and preserved source data/backups. Compare v1 preference/progress outcomes without assuming JSON preference conversion or historical HTTP progress restoration. If a path mismatch is reproduced, add only a path-compatibility patch with a failing regression test and rerun the matrix; stop for approval if preserving semantics requires more than packaging compatibility.
- [ ] **Step 5: Verify interim integration and write final user notes.** With both app IDs installed, establish that the current released companion still targets `app.motrix.native`, not this package; do not label that a downstream pairing pass. Notes must cover the retained private directory versus non-guaranteed v1 conversion, user-confirmed paused import, explicit activation, permission/override changes, backup/recovery requirements, ordinary downloads working without integration, and the need for an explicitly selected compatible future companion. Link the upstream PR only once it exists. Do not prescribe installing the current companion for this ID or distribute an alternate host installer.
- [ ] **Step 6: Record acceptance and review checkpoint.** Record commands, worker architectures, exact package/PR head SHAs and outcomes in the maintainer section of `docs/migration-v2.md`; record anything not executable as a blocker. Require both architecture builds, installed validation, broker probe, real-profile/UI checks and updater exercises before calling the package ready. If authorized, commit only documentation and any independently verified compatibility fix; never commit private fixtures/build artifacts.

## Planning evidence and limits

The pinned upstream recipe, workflow, TypeScript identity code/tests and Rust companion/broker sources were inspected through GitHub. Upstream default HEAD was `6099f17c585e5accb45972283a638229f24ab64b` during planning. External-data-checker's documented offline syntax is `--lint MANIFEST`; the anchored Git checker avoids depending on newer published-release checker deployment.

Terminal execution failed before running Git: `bwrap: execvp ... zed-editor (deleted): No such file or directory`. No build, test, Git status, workflow execution or CLI validation was performed while writing this plan. Restore terminal execution or use approved CI at execution time. The exact upstream recipe—not generic Electron packaging advice—is authoritative for this migration.
