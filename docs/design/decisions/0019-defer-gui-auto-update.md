# ADR 0019: Defer GUI Auto-Update to Post-Phase-8

**Date**: 2026-08-06  
**Status**: Accepted

## Context

Phase 8 ROADMAP lists "自动更新：tauri-plugin-updater，GitHub Releases 签名更新"
under 7B advanced features. The `tauri-plugin-updater` requires:

1. A signing key pair (private key for CI, public key embedded in app)
2. GitHub Releases integration with update manifest JSON
3. A `tauri-plugin-updater` dependency and IPC command wiring
4. CI workflow changes to sign and upload update bundles

The Phase 8 exit condition states "7C 扩展功能可 deferred 到后续 Phase".
Auto-update is a distribution/operations feature, not a core GUI functionality
feature. It does not affect scanning, detection, or user interaction with the
application.

## Decision

Defer `tauri-plugin-updater` auto-update to a post-Phase-8 improvement.

**Rationale**:
- Auto-update is a release infrastructure concern, not a GUI feature
- It requires signing key management which is an operational decision
- Users can manually download new versions from GitHub Releases
- Phase 8 exit condition explicitly allows deferring non-core features
- Implementing it now would block Phase 8 closure on an operational dependency

## Consequences

- Users must manually check for updates via GitHub Releases
- The `tauri-plugin-updater` integration will be implemented in a future
  phase when signing infrastructure is established
- This ADR serves as the formal deferral record required by the ROADMAP

## Implementation Plan (Future)

1. Generate Ed25519 signing key pair
2. Add `tauri-plugin-updater` dependency
3. Configure updater in `tauri.conf.json` with public key
4. Add "Check for Updates" menu item
5. Update CI to sign bundles and generate update manifests
6. Test update flow on all three platforms
