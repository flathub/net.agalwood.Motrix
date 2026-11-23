# Flatpak Host Companion Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Propose upstream support for explicitly installing the host companion for either known Motrix Flatpak identity without weakening its trust boundary.

**Architecture:** Add a closed two-value app-ID type, persist the selected identity in the existing protected configuration, and thread that type into broker and launch commands. Missing configuration fields retain upstream behavior; changing an existing installation's target requires explicit replacement consent. This is an independent upstream contribution, not a host binary shipped by the [downstream migration](2026-11-23-upstream-flatpak-adoption.md).

**Tech Stack:** Rust, Serde, existing native-host unit/process tests, upstream Flatpak protocol smoke checks.

**Spec:** `docs/superpowers/specs/2026-11-22-upstream-flatpak-adoption-design.md`, especially “Separate upstream companion PR.”

## Global Constraints

- Restrict app IDs to `app.motrix.native` and `net.agalwood.Motrix`; default to `app.motrix.native` for backward compatibility.
- Do not auto-select between two installed apps or silently replace existing integration.
- Preserve exact-ID validation, absolute path checks, extension allowlists, broker framing and nonce checks intact.
- Preserve existing config compatibility and reject unknown IDs.
- No downstream host-companion binary distribution or host-side installation from inside the Flatpak.
- No spoofing `FLATPAK_ID`, host escape, broader D-Bus access, or weakened broker/caller validation.
- Draft against current upstream HEAD, not a release-only checkout; recheck architecture before implementation.
- The install-time API below is a proposal requiring user/upstream review, not an already agreed upstream interface. Adapt spelling to upstream feedback without broadening the fixed-ID trust boundary.
- No commits, branches, fork, push or PR publication without explicit authorization. Plan approval does not by itself authorize those operations. Downstream release need not wait for this PR; a merged PR is not a released companion binary.

## Review Focus

1. A schema-v1 configuration lacking an app ID must still load and target the upstream application — Task 1 legacy-deserialization test.
2. Missing/duplicate/unknown/non-UTF-8 IDs and hand-edited invalid config must fail before commands or installation writes — Task 1 parser/config tests.
3. Re-running an installer with both apps present must preserve the previous selection unless a different ID and `--force` are explicit — Task 1 replacement tests.
4. Broker probe, endpoint wait and application launch must all use the same selected ID, never a browser argument or environment override — Task 2 fake-process argv tests.
5. An otherwise valid selection must not bypass unsafe-file, caller, framing, timeout, or nonce checks — Task 2 negative regression and protocol checks.

---

## Repository boundary and file map

All `packages/`, `.github/` and `flatpak/` paths below are in a separate checkout of `https://github.com/agalwood/Motrix.git`, **not this Flathub repository**. Do not put upstream application code or a companion binary into the packaging repository.

| File                                                                | Responsibility                                                                           |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Create `packages/native-host/src/flatpak_companion/app_id.rs`       | Closed identity type, strict parsing/Serde and upstream default                          |
| Modify `packages/native-host/src/flatpak_companion.rs`              | Export the new type; keep other protocol constants unchanged                             |
| Modify `packages/native-host/src/flatpak_companion/command.rs`      | Explicit optional `install --app-id` selection                                           |
| Modify `packages/native-host/src/flatpak_companion/installation.rs` | Protected configuration, consented replacement, status selection                         |
| Modify `packages/native-host/src/flatpak_companion/runtime.rs`      | Typed target for all `flatpak run` commands                                              |
| Modify `packages/native-host/src/bin/motrix-flatpak-native-host.rs` | CLI wiring, help and selected-ID status display                                          |
| Modify `packages/native-host/src/flatpak_companion/tests.rs`        | Existing parser/config/filesystem/process test coverage                                  |
| Modify `packages/native-host/README.md`                             | Install/upgrade/target-selection and release limitations                                 |
| Modify `.github/workflows/flatpak.yml`                              | Retain default-ID installed-companion smoke and explicitly test default selection status |

Do not change upstream's application/broker `MOTRIX_FLATPAK_ID` constant in `packages/native-host/src/lib.rs` to accept arbitrary IDs. The Flathub build patches its own broker identity separately.

## Task 1: Model and persist the explicitly selected application

**Interfaces:**

- `FlatpakAppId`: `Upstream` and `Flathub` variants, `Copy`, `Eq`, `Debug`, Serde; exact serialized strings `app.motrix.native` and `net.agalwood.Motrix`; `Default` is `Upstream`.
- `FlatpakAppId::as_str(self) -> &'static str`; `FromStr<Err = CompanionError>` accepts only those strings. Export through `flatpak_companion.rs`.
- `CompanionCommand::Install { flatpak_bin: PathBuf, app_id: Option<FlatpakAppId>, force: bool }`; `None` means preserve a valid owned existing selection, otherwise upstream default for a new installation.
- `CompanionConfig` adds private `app_id: FlatpakAppId`, serialized as `appId` with a missing-field default, and `app_id(&self) -> FlatpakAppId`. Retain schema version `1`, existing ownership fields and `deny_unknown_fields`.
- `install_companion(paths: &CompanionPaths, source_executable: &Path, flatpak_bin: &Path, app_id: Option<FlatpakAppId>, allowlist: &NativeMessagingAllowlist, force: bool) -> Result<(), CompanionError>`.
- `CompanionStatus` adds `app_id: Option<FlatpakAppId>`; populate only from a valid owned configuration. Preserve `installed`/`issues` behavior.

**Files:** `app_id.rs`, `flatpak_companion.rs`, `command.rs`, `installation.rs`, `tests.rs`, CLI install/status call sites and existing call sites in those files.

- [ ] **Step 1: Rebase the plan's assumptions on current upstream HEAD.** Read repository instructions and current versions of the files above; record the immutable starting commit. Planning observed HEAD `6099f17c585e5accb45972283a638229f24ab64b`, but execution must recheck. If upstream already supports target selection, adapt/tests-review that implementation instead of duplicating it; escalate only if the architecture invalidates the agreed scope. Prepare an isolated upstream worktree only with the required authorization.
- [ ] **Step 2: Add failing identity/parser tests to `tests.rs`.** Add `app_id_accepts_only_known_exact_values`, `install_cli_parses_optional_app_id`, and `install_cli_rejects_bad_app_id_arguments`. Assert both exact values round-trip, default is upstream, omission produces `None`, and unknown/case-changed/empty/missing-value/duplicate/non-UTF-8 input errors. Keep `--flatpak-bin` absolute-path validation and existing duplicate flag behavior.
      Core assertions for `app_id_accepts_only_known_exact_values` (import `FlatpakAppId` from `super`):

  ```rust
  assert_eq!(FlatpakAppId::default(), FlatpakAppId::Upstream);
  assert_eq!("app.motrix.native".parse::<FlatpakAppId>().unwrap(), FlatpakAppId::Upstream);
  assert_eq!("net.agalwood.Motrix".parse::<FlatpakAppId>().unwrap(), FlatpakAppId::Flathub);
  assert_eq!(FlatpakAppId::Flathub.as_str(), "net.agalwood.Motrix");
  assert!("net.agalwood.motrix".parse::<FlatpakAppId>().is_err());
  assert!("org.example.Other".parse::<FlatpakAppId>().is_err());
  ```

- [ ] **Step 3: Run `cargo test --manifest-path packages/native-host/Cargo.toml --locked flatpak_companion`.** Expected: new tests fail to compile until the new type/field exists; distinguish this expected failure from environment/dependency problems.
- [ ] **Step 4: Implement the closed type and parser.** Add the Interfaces above; reject invalid values before invoking installation. Update CLI destructuring and existing install call sites mechanically so this task remains buildable. Leave runtime targeting unchanged until Task 2.
- [ ] **Step 5: Add failing protected-config and replacement tests.** Add `legacy_config_defaults_to_upstream`, `config_rejects_unknown_app_id`, `install_round_trips_both_app_ids`, `reinstall_without_id_preserves_selection`, and `changing_owned_target_requires_force`. Use existing temporary/private-file fixtures. Assert a missing `appId` in schema-v1 loads as upstream; both IDs persist as exact strings with config mode `0600`; invalid/null/wrong-type IDs fail load/status; all existing filesystem ownership checks remain active. Changing a valid owned selection without `--force` must fail before changing any file; explicit different ID plus `--force` succeeds. Omitted ID never discovers/selects an installed Flatpak, even with `--force`. An invalid existing configuration still follows current unowned-config/force handling, never becomes a trusted source of an ID.
- [ ] **Step 6: Run the focused command again and observe the new config/consent failures.** Expected: parser tests now pass; persistence/replacement assertions fail.
- [ ] **Step 7: Implement persistence, status and consent checks before writes.** Extend `CompanionConfig::new` to take the typed ID. Derive an effective ID from explicit selection, then valid owned existing config, then upstream default. Validate target-change consent before copying binary/config/manifests. Keep canonical executable validation, secure parent traversal, atomic write ownership and uninstall semantics unchanged. Update CLI status to print `app-id: <exact-id>` for valid configuration; preserve the existing installed/not-installed lines and exit statuses.
- [ ] **Step 8: Run focused tests and review the compatibility boundary.** Expected: all `flatpak_companion` tests pass, including existing security tests. New binaries read old configs; an old binary's `deny_unknown_fields` will reject a new `appId` field, so document rollback/reinstallation rather than promising old-binary forward compatibility. Do not weaken strict config parsing.
- [ ] **Step 9: Review checkpoint.** If commits are authorized, commit only this task's files with message `feat: persist an explicit known Flatpak companion target`.

## Task 2: Route broker/launch consistently and prove unchanged protocol security

**Interfaces:** `FlatpakProcessRuntime::new(flatpak_bin: PathBuf, app_id: FlatpakAppId) -> Self`; private runtime field `app_id: FlatpakAppId`. Task 1's `CompanionConfig::app_id()` is the sole browser-mode selection source. Existing `FlatpakRuntime` trait and resolver behavior remain unchanged.

**Files:** `runtime.rs`, `tests.rs`, `src/bin/motrix-flatpak-native-host.rs`, `packages/native-host/README.md`, `.github/workflows/flatpak.yml`.

- [ ] **Step 1: Extend failing fake-process tests.** Parameterize `process_runtime_uses_fixed_flatpak_commands_and_rejects_stdout_pollution` over both typed IDs. Assert exact argv: broker `run --command=motrix-native-host-broker <selected-id>` and launch `run <selected-id>`, with no shell or additional arguments. Exercise both `Probe` and `WaitForEndpoint` using operation-valid responses, and preserve failure cases for stdout pollution and operation-invalid responses. Add `runtime_selection_ignores_environment_and_browser_payload`: malicious ID-like request fields cannot change the selected argv. Avoid mutating process-global environment in parallel tests; use an isolated child-process fixture when testing environment variables.
- [ ] **Step 2: Run `cargo test --manifest-path packages/native-host/Cargo.toml --locked flatpak_companion`.** Expected: selected-Flathub process assertions fail or the new constructor signature is absent.
- [ ] **Step 3: Thread the typed selection into runtime and CLI browser mode.** Both command builders use `self.app_id.as_str()`. Construct runtime from validated `config.flatpak_bin()` and `config.app_id()`, after existing browser-caller validation. Do not modify broker protocol, launch consent, process-group handling, output limits/timeouts or response validation. Keep default upstream broker identity constant untouched.
- [ ] **Step 4: Run complete native-host checks.** Run `cargo test --manifest-path packages/native-host/Cargo.toml --locked --all-targets`, `cargo fmt --manifest-path packages/native-host/Cargo.toml --check`, and `cargo clippy --manifest-path packages/native-host/Cargo.toml --locked --all-targets -- -D warnings`. Expected: success, including existing allowlist, unsafe-path/symlink/writable-parent, framing, nonce and timeout-related coverage. Use the current upstream toolchain and dependency instructions; report unavailable checks honestly.
- [ ] **Step 5: Update documentation and default-ID smoke coverage.** Document `motrix-flatpak-native-host install --app-id net.agalwood.Motrix`, upstream default, omitted-ID reinstall preservation, explicit `--force` to switch targets, unchanged browser manifest host name, protected config, and old-binary rollback caveat. Explain that both apps installed never causes auto-selection and that Flathub compatibility requires a patched/compatible broker plus a released companion. In upstream's existing `.github/workflows/flatpak.yml` smoke, assert the installed default companion's status reports `app-id: app.motrix.native` and keep the existing framed browser exchange intact; do not claim its unmodified upstream Flatpak tests the retained Flathub ID.
- [ ] **Step 6: Run protocol smoke checks at the appropriate boundary.** Run upstream's existing Flatpak workflow for default-ID payload/companion exchange. In a disposable environment with the downstream plan's tested retained-ID build, explicitly install the newly built companion for `net.agalwood.Motrix` and adapt the existing nonce-server/framed Native Messaging exchange from upstream's workflow, changing only installation selection and target ID. Assert valid `requestPair` framing/port/nonce and refusal of an unallowlisted caller. With both apps present, capture argv to prove only the selected target is invoked. If the downstream build or desktop/browser environment is unavailable, record the cross-repository smoke as unperformed, not a prerequisite already satisfied by unit tests.
- [ ] **Step 7: Review checkpoint.** If authorized, commit runtime/tests/docs/workflow with message `fix: route companion broker and launch to the selected Flatpak`.
- [ ] **Step 8: Prepare the upstream PR handoff.** Summarize the fixed-ID trust boundary, migration of old configs, target-switch consent, test evidence and unexecuted checks. Seek approval of the proposed API before publication. Only with explicit branch/fork/push/PR authorization, submit against current upstream HEAD and link the resulting PR in downstream `docs/migration-v2.md`. Do not change the downstream interim warning until a compatible companion binary is actually released and verified.

## Planning evidence and limits

The upstream parser, protected configuration/installer, runtime, CLI, shared ID constant and existing test fixtures were inspected at the planning baseline. The current installer accepts only `--flatpak-bin` and `--force`; runtime launch and broker both use the fixed shared upstream ID. These exact seams motivate the closed-type proposal above.

No upstream checkout was modified and no branch, commit, fork, PR, binary, build or test was created/run during planning. The local terminal cannot start because Zed's sandbox points to a deleted executable; execution needs restored tooling or approved CI. The downstream migration remains independently shippable with browser integration explicitly unavailable.
