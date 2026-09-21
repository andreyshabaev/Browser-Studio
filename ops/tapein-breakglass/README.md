# Tape In Break-Glass Recovery

Independent recovery path for Tape In Control. This path MUST NOT depend on Control, QueueV2, Registry bootstrap, Browser Studio runtime, or the legacy Drive queue.

## Contract

Primary path: ChatGPT -> normal Control/QueueV2.

Break-glass path: GitHub Actions -> SSH -> Selectel host -> guarded installer.

The break-glass workflow is manual-only (`workflow_dispatch`) and uses a dedicated SSH credential with least privilege. The server-side account is restricted to `/usr/local/sbin/tapein-breakglass-install` via `authorized_keys` forced-command or sudoers. It cannot execute arbitrary shell.

Every install requires:
- exact expected current build;
- exact candidate SHA-256;
- immutable candidate URL/Drive artifact prepared beforehand;
- automatic copy of current Control to rollback path before mutation;
- syntax/self-test before cutover;
- atomic replacement;
- service/timer restart and post-install build check;
- automatic rollback on failure.

## Required GitHub environment secrets

`TAPEIN_BREAKGLASS_HOST`
`TAPEIN_BREAKGLASS_USER`
`TAPEIN_BREAKGLASS_SSH_KEY`
`TAPEIN_BREAKGLASS_HOST_KEY`

These secrets are deliberately outside Tape In Control. Control cannot rotate or delete them.

## Permanent rule

Never remove this recovery path during Control migrations. Any Control release that changes queue/bootstrap logic must prove this path still works before promotion.
