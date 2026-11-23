# Adopt upstream Motrix Flatpak packaging

Status: proposed; awaiting user approval.

## Intent and agreed decisions

Migrate this Flathub package from Motrix v1.8.19 to upstream v2.4.5 while keeping `net.agalwood.Motrix`. Prefer upstream-owned packaging inputs and maintain only necessary Flathub compatibility here.

The user agreed to:

- Retain the existing Flatpak application ID.
- Adapt upstream's Flatpak build recipe, not retain the old Yarn build.
- Copy upstream's committed Node and Cargo source lists from the exact application commit using a GitHub workflow rather than regenerate them downstream.
- Consume upstream desktop and metainfo files without independently maintained copies.
- Follow upstream's Downloads-plus-file-chooser-portals permission policy rather than retain broad home access.
- Patch upstream's hardcoded Flatpak identity for this package.
- Pursue a separate upstream PR for host-side companion compatibility. Accept unavailable browser integration in this Flathub build until a compatible companion is released; upstream PR merge alone does not update installed companion binaries.

This is a multi-file packaging migration, with a separate upstream compatibility contribution. Neither implementation nor publishing begins before design approval. No commits or branches are created without explicit authorization; the requested upstream PR will require its own branch/fork as appropriate after approval.

## Goals, non-goals, and anti-goals

### Goals

- Build v2.4.5 offline for x86_64 and aarch64 using upstream's tested packaging contract.
- Preserve the Flathub identity, desktop export identity, and existing sandbox data directory.
- Keep application source, dependency lists, build tool versions, engine, and signed plugin artifacts consistent.
- Minimize duplicated desktop metadata and dependency-generation machinery.
- Clearly document the temporary browser-integration limitation and v1 migration implications.

### Non-goals

- No downstream host-companion binary distribution or host-side installation from inside the Flatpak.
- No spoofing `FLATPAK_ID`, host escape, broader D-Bus access, or weakened broker/caller validation.
- No additional downstream migration wrapper, forced legacy import, profile relocation, deletion, or database reset. Preserve upstream's automatic discovery/invitation and supported automatic settings/database migrations unchanged.
- No promise that arbitrary future upstream build-recipe changes can be updated without review.
- No unrelated packaging cleanup or application feature work.

### Anti-goals

- Do not describe keeping the package ID as seamless v1 data migration.
- Do not claim browser integration works with upstream's current unmodified companion.
- Do not update engine, pnpm, Electron, or plugin dependencies independently of upstream's application release contract merely because newer versions exist.

## Approaches considered

1. **Selected: upstream-owned inputs plus narrow downstream adaptation.** Adapt the tagged manifest; synchronize upstream dependency lists; install upstream metadata with identity adjustments. Seek upstream support for the retained ID in the separately installed companion, accepting temporary unavailability. This minimizes downstream ownership but depends on an upstream companion release for browser integration.
2. **Downstream regeneration and companion distribution.** Reproduce upstream's specialized generator pipeline and ship patched host companions separately. This avoids waiting on upstream but creates ongoing generator and host-binary release maintenance; rejected as contrary to the user's goal.
3. **Adopt `app.motrix.native` wholesale.** Closest to upstream but changes application identity and update channel; rejected by the user's explicit constraint.

## Verified baseline

- Application repository: `https://github.com/agalwood/Motrix.git`.
- Tag: `v2.4.5`.
- Peeled application commit: `6099f17c585e5accb45972283a638229f24ab64b` (not annotated tag object `0edbc7f9a7a01c097a9c4f8ffeeac9cf9b5eba5b`).
- Runtime and Electron BaseApp remain Freedesktop 25.08.
- Upstream uses Node 24, pnpm 12.21.0, Electron 45.3.3 headers, pinned architecture-specific Rust toolchains, and aria2 `v1.37.0-motrix.25` with c-ares/libssh2 dependencies.
- Upstream's `flatpak/generated-sources.json` prepares a pnpm v11 store, not a Yarn mirror. `flatpak/cargo-sources.json` covers both native-host and finalize-fs lockfiles.
- Upstream's Flatpak workflow regenerates and compares committed source lists, builds both architectures, checks the installed broker, and performs an x86_64 framed host-companion exchange. This does not replace interactive desktop/browser testing.
- Current downstream automation selects modules by numeric index and runs Yarn generation on push. Replace that workflow rather than extend its assumptions.

## Downstream package design

### Manifest and offline inputs

Use upstream `flatpak/app.motrix.native.yml` at the pinned application commit as the initial recipe. Replace its placeholder application source with the public repository, tag, and peeled commit. Keep module name `motrix` so upstream's `/run/build/motrix/...` paths remain valid.

Retain `net.agalwood.Motrix` and the existing manifest filename. Carry over upstream dependency modules, staging order, offline build steps, signed builtin-plugin inputs, wrapper behavior, and broker installation. Preserve upstream's `xdg-download`, Wayland/X11, network, graphics and portal policy. Remove assumptions about i386/armv7 support; this recipe targets x86_64/aarch64.

Store `generated-sources.json` and `cargo-sources.json` locally alongside the manifest. Flatpak resolves string includes before it downloads/extracts application sources, so these cannot be references to files that only appear inside the eventual upstream checkout.

Use stable-release source tracking through `x-checker-data`. The documented Git checker with an anchored three-component stable tag pattern is the baseline; a published-release checker may be selected if supported by the deployed external-data-checker. Verify syntax with its linter before choosing. Do not add independent updates for coupled engine/plugin/toolchain inputs that would invalidate upstream's checks.

### Identity compatibility patch

Maintain a small, reviewable patch applied before compilation. Audit production identity references and change only the desktop/Flatpak identity contracts needed for `net.agalwood.Motrix`, including:

- `src/main/bridge/flatpak-environment.ts`: recognize the actual retained ID.
- `packages/native-host/src/lib.rs`: adapt the shared `MOTRIX_FLATPAK_ID` used by the in-sandbox broker's bridge-directory and launch checks.
- `src/shared/constants.ts`: audit `APP_ID` callers and align desktop identity where needed; do not rename protocol/service identifiers merely because they have an `app.motrix` prefix.

Keep exact-ID validation, absolute path checks, extension allowlists, broker framing and nonce checks intact. Do not globally replace arbitrary branding, protocol names, or all strings in the repository. Adjust relevant upstream tests/fixtures in the patch where required and run targeted checks. The host companion is not installed into the Flatpak; patching its shared constant in this source tree does not change upstream's separately downloaded binary.

### Desktop and AppStream metadata

Install `flatpak/app.motrix.native.desktop` and `flatpak/app.motrix.native.metainfo.xml` directly from the pinned checkout. Use targeted build-time transformations (or verified Flatpak rename support) to produce:

- `net.agalwood.Motrix.desktop`, with `Icon=net.agalwood.Motrix`.
- `net.agalwood.Motrix.metainfo.xml`, with component ID `net.agalwood.Motrix` and launchable `net.agalwood.Motrix.desktop`.

Keep `Exec=start-motrix %U` and upstream's current WM class unless runtime testing establishes a required adjustment. Install the upstream application icon under the retained ID. Retain upstream descriptions, screenshots, developer identity, license and release history. Remove the downstream desktop/metainfo copies only once the manifest no longer references them. Do not attempt to update upstream metainfo at a nonexistent local file path in the updater.

### Update workflow

Replace `.github/workflows/auto-update.yml` with a source-sync workflow suitable for trusted same-repository update PRs, plus manual dispatch. Locate the application source by module name and repository URL, never numeric module index.

For a changed application source commit:

1. Validate the tag/commit relationship and fetch files using the immutable manifest commit.
2. Copy the two upstream source lists into the PR branch, requiring successful retrieval and valid nonempty JSON.
3. Inspect changes in the corresponding upstream Flatpak recipe against the previous application revision. Coupled pins and build commands are not silently assumed compatible: report those differences for maintainer review and leave the PR blocked/failing if the local adaptation is no longer consistent. The implementation may automate mechanically safe pin synchronization, but must not silently discard downstream adaptations or treat a dependency-list copy as a complete build-recipe update.
4. Commit only intended generated-source updates to the trusted PR branch; never push to a fork with a write token or run PR-provided code with elevated credentials. Use least-privilege token permissions and validate inputs passed into shell commands.
5. Ensure updated PR contents receive Flathub validation. Do not assume a push using `GITHUB_TOKEN` retriggers every workflow; document any manual action or GitHub App token needed for the selected event design.

Keep the synchronization lean; Flathub build validation remains authoritative for the resulting package. No vendored generator toolchain is needed.

### Existing users and permissions

The package update retains `~/.var/app/net.agalwood.Motrix/`. Preserve upstream's migration behavior, including automatic discovery of recognizable legacy profiles and its one-time Migration Assistant invitation under upstream's consent/onboarding conditions. Keep upstream's automatic internal settings and application/engine database upgrades enabled. Do not add a separate downstream migration wrapper or force user-confirmed legacy imports to run silently.

Upstream's Linux discovery checks `$XDG_CONFIG_HOME/Motrix` and `~/.config/motrix`. Retaining the Flatpak ID keeps the application's own private configuration accessible even with Downloads-only filesystem permissions. Verify detection against a disposable copy of an actual v1 Flatpak profile; do not assume detection succeeds solely because the ID is retained. If an upstream discovery-path mismatch prevents recognition, make the smallest packaging compatibility adjustment while preserving upstream's consent and import semantics.

Distinguish these mechanisms in migration notes: automatic internal settings-schema upgrades do not establish general conversion of v1's `user.json`/`system.json` preferences to v2's `settings.json`. Upstream's v1 task import requires user selection/confirmation, imports paused records, and requires explicit activation before transfer. Preserve legacy source files and downloads according to upstream's behavior, and retain verified database backups for downgrade/recovery. Do not promise all v1 preferences or historical HTTP progress migrate automatically.

New manifest defaults grant Downloads access, not home access. Existing destinations elsewhere may require explicit re-selection through the portal. Existing user permission overrides can remain effective; changing manifest defaults is not a mechanism for deleting user overrides. Call out this behavior in downstream migration notes.

## Separate upstream companion PR

### Scope and proposed interface

The user selected upstream compatibility instead of downstream companion distribution. Upstream's released companion currently always invokes `flatpak run app.motrix.native`; installer options only support the Flatpak executable path and force replacement.

Proposed upstream design (agent recommendation, not an already agreed API): add an explicit install-time app-ID choice restricted to the two known Motrix IDs, persist it in the protected companion configuration, and use it consistently for broker invocation, application launch and status. Default to `app.motrix.native` for backward compatibility. Preserve existing config compatibility and reject unknown IDs. Do not auto-select between two installed apps or silently replace existing integration.

Include tests covering both IDs, legacy configuration/default behavior, invalid IDs, launch/broker argument construction, and unchanged security checks; update companion installation documentation. Adapt to upstream's preferred API after review without changing the fixed-ID trust boundary. Draft the upstream PR against current upstream HEAD, rechecking the code since v2.4.5. Link it from downstream migration notes when available.

### Interim behavior and ownership

Ship the Flathub migration without working browser Native Messaging integration while waiting. Document that current upstream companions target the other application and must not be presented as compatible. Do not register browser manifests inside the Flatpak or bundle an alternate host installer. Once upstream publishes a compatible companion, users install/update it explicitly for `net.agalwood.Motrix`; ordinary downloading remains available without it.

## Validation and acceptance

Before declaring the package ready:

- Parse and resolve the complete manifest with `flatpak-builder --show-manifest`.
- Lint external-data-checker metadata and the Flatpak manifest.
- Validate the installed/generated desktop and metainfo files and their IDs.
- Confirm identity patch applies to the pinned commit and run focused upstream identity/broker tests where tooling permits.
- Build offline on both x86_64 and aarch64, verifying source-built aria2 features, native helpers, retained export identity and wrapper behavior.
- Probe the broker under `net.agalwood.Motrix` and confirm the expected not-running response rather than an invalid-ID rejection.
- Interactively test ordinary downloads, file chooser access outside Downloads, Wayland/X11 startup, and a disposable copy of a real v1 Flatpak profile. Verify upstream's automatic legacy discovery/invitation under its consent conditions, confirmed paused import, and supported internal settings/database upgrades remain functional. Do not claim browser pairing passes during the interim.
- Exercise source-sync logic on a trusted disposable/manual update path, including failed downloads, tag/commit mismatch and upstream recipe drift.
- For the separate upstream PR, run its relevant companion unit tests and protocol smoke checks, recording anything not executable locally.

At design time, terminal commands cannot start because Zed's sandbox references a deleted executable. GitHub and file tools work. Builds and command-line validation remain unperformed; restore terminal execution or use approved CI before making validation claims.

## Left to the builder

Choose the smallest metadata transformation mechanism that passes validation; exact workflow filename and safe event/token implementation; patch filename; how to surface upstream recipe drift; focused test commands; and minimal migration-note location. These choices must preserve the constraints above. Escalate only if upstream's current companion architecture or actual legacy-profile behavior invalidates the agreed scope.

## Primary references

- https://github.com/agalwood/Motrix/blob/v2.4.5/flatpak/app.motrix.native.yml
- https://github.com/agalwood/Motrix/blob/v2.4.5/.github/workflows/flatpak.yml
- https://github.com/agalwood/Motrix/blob/v2.4.5/packages/native-host/README.md
- https://github.com/agalwood/Motrix/blob/v2.4.5/packages/native-host/src/flatpak_companion/runtime.rs
- https://github.com/agalwood/Motrix/blob/v2.4.5/packages/native-host/src/flatpak_companion/command.rs
- https://github.com/agalwood/Motrix/blob/v2.4.5/docs/legacy-migration.md
- https://github.com/agalwood/Motrix/blob/v2.4.5/src/main/legacy-import/navigation-state.ts
- https://github.com/agalwood/Motrix/blob/v2.4.5/src/main/legacy-import/desktop-import.ts
- https://github.com/agalwood/Motrix/blob/v2.4.5/src/core/settings/settings-manager.ts
- https://github.com/flathub/flatpak-external-data-checker#git-checker
