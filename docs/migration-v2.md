# Motrix v2 Flatpak migration

> **Release acceptance is incomplete.** This is an uncommitted packaging adaptation,
> not a verified release. See the acceptance record below before publishing.

## Existing users

The package keeps **`net.agalwood.Motrix`** and its private directory,
`~/.var/app/net.agalwood.Motrix/`. Keeping that directory is **not a guarantee of
seamless v1 conversion**.

Before upgrading, stop Motrix and preserve a restorable copy of the entire old
private directory, application/settings/engine databases, legacy `user.json` and
`system.json`, and the actual download files (including those outside Downloads).
Record existing Flatpak permission overrides. Test restoration in a separate
account or VM before relying on a downgrade: an older application may not read
an upgraded database. Do not delete the legacy files or restore over the only
remaining copy. No downstream wrapper relocates profiles, resets databases,
forces imports, or deletes permission overrides.

Upstream automatically discovers recognizable legacy data and may offer a
one-time Migration Assistant invitation, subject to its onboarding/consent
conditions. Its Linux discovery searches `$XDG_CONFIG_HOME/Motrix` and
`~/.config/motrix`; discovery from an actual v1 Flatpak profile still needs to be
verified. Task import requires explicit selection and confirmation, creates
**paused** records, and requires explicit activation before transfers start.
Supported automatic internal settings-schema and application/engine database
upgrades remain enabled. These mechanisms do not establish general conversion
of v1 JSON preferences into v2 `settings.json`, or restoration of all historical
HTTP download progress. Preserve the original data and verified database backups.

### File access

New defaults allow Downloads, not the whole home directory. For destinations
elsewhere, explicitly select the directory through the file chooser portal.
An existing destination outside Downloads may need to be selected again.
Existing user overrides may still grant broader access; the new manifest does
not silently delete them. Review overrides deliberately rather than assuming the
new defaults revoke previous grants.

### Browser integration is temporarily unavailable

Ordinary in-app downloading does not require a browser companion. The current
upstream companion targets **`app.motrix.native`**, not this Flathub ID. Installing
it is not a solution for this package and may route to the other Motrix when both
are installed. No successful downstream browser pairing is claimed.

Wait for a compatible companion release and explicitly select
`net.agalwood.Motrix` when installing/updating that future companion. An upstream
PR merge alone does not update an installed binary. This package installs no
browser-facing Native Messaging host or browser manifests and does not install
anything on the host from inside the sandbox. A separate compatibility PR has
not been created; there is no PR link or alternate host installer to recommend.

## Maintainer update procedure

The application release owns the engine, Node/pnpm/Electron/Rust versions,
signed builtin plugins, dependency pins and offline build order. Do not update
these independently. Both root JSON lists are byte-for-byte copies of the
application commit's `flatpak/` files; there is no downstream generator.

1. Prepare an open, same-repository PR targeting the default branch, authored by
   `flathubbot` or a collaborator whose API permission is write/maintain/admin.
   Select the unique `motrix` module's git source at
   `https://github.com/agalwood/Motrix.git`, with a stable `vN.N.N` tag and its
   **peeled commit**, not an annotated tag object. Module indexes are not stable.
2. The source-sync workflow executes only the helper from the trusted base
   revision, never the PR checkout. Fork PRs skip the write-capable job. Manual
   dispatch must run from the default branch and takes a numeric PR number.
   `GH_TOKEN` is passed only to the trusted helper; no new App/PAT secret is
   required. Default CLI behavior is check-only:

   ```sh
   python3 .github/scripts/sync_upstream_sources.py --repository flathub/net.agalwood.Motrix --pr 123
   ```

   Replace `123` with the actual disposable/release PR number. The helper reads
   PR files through immutable GitHub API references; it never changes local
   source lists or runs their contents.

3. A changed upstream recipe produces a Markdown diff and exact new recipe
   SHA256 in the Actions summary, then fails closed. Review all changes,
   including engine pins, signatures, toolchains, commands, wrappers and
   permissions. Update the PR manifest to the complete adaptation of the new
   recipe; refresh/check the identity patch against the new application commit.
   The only automatic adaptations are retained IDs, application source/checker,
   removal of aria2's independent checker, insertion of the identity patch,
   local source-list includes, and guarded checkout-metadata installation.
4. Only after review, manually dispatch **Sync upstream sources** from the
   default branch with the PR number and `reviewed_recipe_sha256` set to the
   exact digest shown. This acknowledgement does not bypass structural equality
   with the adapted new recipe. A missing old recipe (v1-to-v2 bootstrap) also
   requires explicit review/digest acknowledgement, not an empty comparison.
   A digest is never read from PR files, labels or automatic PR events.
5. The helper validates the tag/commit, both bounded JSON downloads, recipe and
   local adaptation before any write. It rechecks PR trust/state/head/base, then
   uses GitHub's atomic `createCommitOnBranch` mutation with `expectedHeadOid`
   set to the validated head. At most one commit changes only
   `generated-sources.json` and `cargo-sources.json`. A concurrent advance or
   rewind refuses writeback rather than restoring removed commits; retry after
   reviewing the new head. This intentionally replaces a non-forced REST ref
   update, which is not an atomic expected-head check. Failed preconditions leave
   local files and the PR ref untouched. Matching list blobs produce no commit.
6. **Explicitly request Flathub validation of the resulting head.** A push with
   `GITHUB_TOKEN` does not reliably trigger downstream workflows. This
   repository's [PR #36 bot response](https://github.com/flathub/net.agalwood.Motrix/pull/36#issuecomment-3442148656)
   documents the supported PR comment **`bot, build`**, serviced by Flathub's
   vorarbeiter test builder. Request that build after synchronization, inspect
   its run/checks and confirm they attach to the exact new head SHA before
   merging. Do not accept checks from the pre-sync commit.

### Trusted-workflow bootstrap and disposable exercise

The new helper is not present on the original default-branch base. A workflow
cannot safely execute its own PR's helper with write credentials just to test
it. First make the orchestration available on the default branch through a
separately reviewed, explicitly authorized bootstrap change. Do not weaken the
trusted-base checkout. Deployment/merge and live API writes were not authorized
in this work session.

Once available, use an explicitly authorized **disposable same-repository PR**
to exercise no-op, a successful two-list sync, partial/failed retrieval, tag
mismatch, unreviewed recipe drift, digest-acknowledged but inconsistent
adaptation, and a concurrently advanced head. Verify the successful commit's
file allowlist; forks must have no write path. Offline mock-HTTP tests do not
replace this hosted exercise. Never inject failures into a real release PR.

## Build and release acceptance runbook

Use native workers for **both x86_64 and aarch64**. The pinned recipe uses
Freedesktop/Electron BaseApp 25.08, Node 24, pnpm 12.21.0, Electron 45.3.3 headers,
architecture-specific Rust archives, and source-built aria2
`v1.37.0-motrix.25`. Keep upstream's signed-plugin verification, private broker,
finalize helper, staging/cleanup and portal/bridge-data/TMPDIR wrapper behavior.

On x86_64 (replace architecture and directory with `aarch64` on native ARM):

```sh
flatpak run org.flatpak.Builder --arch=x86_64 --download-only build-x86_64 net.agalwood.Motrix.yml
flatpak run org.flatpak.Builder --arch=x86_64 --disable-download --force-clean build-x86_64 net.agalwood.Motrix.yml
```

Retain logs proving network-isolated build phases and source-built aria2's
feature assertions, including `Sec-WebSocket-Accept`. In a disposable account/VM,
install the test build and validate actual installed desktop/metainfo/icon IDs,
`Exec=start-motrix %U`, upstream WM class, manifest/build lint, native broker and
finalize helper, removed staging, and absence of browser host/manifests. Staged
metadata validation alone is not installed-payload validation.

With Motrix stopped in that disposable environment:

```sh
printf 'MXBR\001\000\000\000\025\000\000\000%s' '{"operation":"probe"}' | flatpak run --command=motrix-native-host-broker net.agalwood.Motrix | od -An -tx1 -v
```

Expected bytes, ignoring whitespace:
`4d584252010000001e0000007b226572726f72223a226d6f747269782d6e6f742d72756e6e696e67227d`
(`motrix-not-running`), not an invalid-environment rejection. Do not spoof
`FLATPAK_ID` or weaken confinement to pass this probe.

Before installing anything, obtain consent for a disposable copy of a **real v1
profile**, including non-Downloads destinations and existing overrides, and
verify backup restoration separately. Record schema versions and layout without
committing personal data. Then exercise:

- Fresh and copied-v1 profiles; ordinary download, pause and resume.
- External destinations through portals; default permissions and preserved
  overrides; secondary-launch handoff; native Wayland and X11 startup.
- Actual legacy-path discovery, onboarding/consent and one-time invitation;
  confirmed paused task import and no transfer before explicit activation.
- Supported settings/application/engine DB upgrades, preserved source files and
  backups, and observed preference/progress outcomes (do not assume conversion).
- Both Motrix IDs installed with the released companion: record that it targets
  the other ID, not a downstream browser-integration pass.

Do not add a migration patch without reproducing a path mismatch and a failing
regression test. Semantics changes beyond narrow packaging compatibility need
approval.

## Acceptance record — 2026-11-23

Application tested: `v2.4.5`, peeled commit
`6099f17c585e5accb45972283a638229f24ab64b`.
Packaging base: `a7d0aee3cfb5f3863c65172082e030ab9e644bbc`.
Implementation branch: `upstream-flatpak-adoption`, **uncommitted**; there is no
final package commit or PR head SHA and no release claim. Validation host:
`x86_64`; identity tests ran inside `org.freedesktop.Sdk//25.08` with locked
upstream dependencies, lifecycle installation scripts disabled, and isolated
ignored caches.

| Check                                                                                              | Observed result                                                                                                                                                                                                                 |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TypeScript identity regressions                                                                    | RED: 3 failed/5 passed before constants; GREEN: 8/8 passed after adaptation                                                                                                                                                     |
| Rust identity regressions                                                                          | RED: retained-ID bridge path rejected; GREEN: full native-host suite, 110/110 including broker/companion integration                                                                                                            |
| Patch                                                                                              | `git apply --check` passed on a separate pristine pinned checkout; changes limited to audited identities and identity fixtures                                                                                                  |
| Structural packaging check                                                                         | RED against v1 recipe; GREEN after adoption, including both byte-equal JSON lists                                                                                                                                               |
| `flatpak run org.flatpak.Builder --show-manifest net.agalwood.Motrix.yml`                          | Passed                                                                                                                                                                                                                          |
| `flatpak run org.flathub.flatpak-external-data-checker --lint net.agalwood.Motrix.yml`             | Passed, 0 errors                                                                                                                                                                                                                |
| `flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest net.agalwood.Motrix.yml`  | Passed with runtime-update warning; 25.08 retained by design                                                                                                                                                                    |
| Exact metadata install/rewrite commands, `desktop-file-validate`, `appstreamcli validate --no-net` | Passed on staged retained filenames; component/icon/launchable IDs, `%U` and unchanged release history asserted                                                                                                                 |
| Offline mock-HTTP sync fixtures                                                                    | 9 methods passed: source selection, exact adaptation, peeled tags, both-list failure atomicity, drift/bootstrap gate, no-op, authorization, concurrent-head refusal and late rewind after the final reread (observed RED→GREEN) |
| `actionlint .github/workflows/sync-upstream-sources.yml`                                           | Passed with digest-verified actionlint 1.7.12                                                                                                                                                                                   |
| Full upstream Vitest suite                                                                         | Not green: 984 files passed, 8 failed, 37 skipped; 14096 tests passed, 4 failed, 249 skipped. Setup/legal/Electron/tooling failures listed below                                                                                |
| Native x86_64 download-only phase                                                                  | Timed out after 120 seconds while downloading locked inputs; no offline build or installation completed                                                                                                                         |
| Native aarch64 build                                                                               | BLOCKED: no native ARM worker provided                                                                                                                                                                                          |
| Installed payload/broker probe                                                                     | BLOCKED: no completed build or disposable installation                                                                                                                                                                          |
| Real-v1 restoration/migration, UI/portal/Wayland/X11/override matrix                               | BLOCKED: no consented real profile, test account/VM or interactive acceptance provided                                                                                                                                          |
| Two-ID released-companion runtime check                                                            | BLOCKED: no disposable dual installation; upstream fixed-ID source was audited, not claimed as a runtime pairing test                                                                                                           |
| Hosted trusted-PR failure/writeback exercise                                                       | BLOCKED: no authorized disposable PR/trusted-base deployment/live writes                                                                                                                                                        |

The broader TypeScript run had failing suites/tests in
`electron-package-contract`, `smoke-electron-cleanup`, `make-resolve-to-mux`,
`liquid-glass`, `operation-service` (finalize-fs build),
`generate-third-party-notices` (two tests; missing Electron license),
`ensure-native-abi` (missing Electron binary), and
`normalize-flatpak-node-sources` (pnpm executable unavailable to subprocess).
These are not a green full-suite result and were not hidden by weakening tests.
The upstream packaging contract is not a downstream acceptance oracle.

Validation-only tests, pristine/patched sources and logs are retained under the
ignored `.flatpak-builder/validation/`; no upstream tree, profile, build output
or packaging test suite is shipped. The Zed sandbox launcher referenced a
deleted executable; commands used explicitly approved unsandboxed execution,
while application tests still ran in the normal SDK sandbox. No commits,
publication, profile changes or live API writes were made.

Independent review found and verified a late-rewind race in non-forced REST
writeback; the atomic expected-head mutation fixes it (regression observed
failing before the fix and passing afterward). A Minor transport-completeness
issue is deferred: a short HTTP body that is still valid JSON (for example,
missing only its final newline) can pass because the helper does not compare
received length with `Content-Length` or verify the upstream Git blob identity.
The demonstrated case does not omit dependencies, but exact HTTP-byte retrieval
is not fully proven by JSON validation alone.

**Release gate:** both native offline builds, installed export and broker checks,
the real-profile/UI matrix, the two-ID interim-integration check and disposable
updater exercise must be recorded against the final package/PR SHA before this
package can be called ready.
