# V03-U1 correction 2 review — source batch accepted

**Decision: the two correction findings are resolved** at `52a09687ab33f88ab0f968460e3adbfb2a2ec50c`. Reviewer: Grok, acting coordinator, independent of Antigravity dispatch `ctx_fb47322f6844`. Codex was not invoked.

The worktree was clean on `codex/v03-ui`. Changed files are `apps/web/src/App.tsx` and `scripts/v03_ui_regressions.js` only.

## What was checked

- Absent observations render "Observed dropout triggers are unavailable for this report." The old threshold claim is gone. The suppression notice renders only when observations exist.
- Hook and pacing render a stored denominator, or "denominator unavailable". The absent fixture does not substitute cast size.
- `main.tsx` still mounts `<App />` with no props. The new optional `initialReport` is the regression seam.
- Independent command, from the UI worktree: `node scripts/v03_ui_regressions.js` then `npm run build`. Both exited 0. The regression rendered both fixtures with `renderToStaticMarkup`. The build used this worktree's Vite 8.3.5 and emitted `apps/web/dist`.

## Still open

Browser upload, playback, live events, deletion, and the 320px journey were not run. Docker's engine pipe is down, so Postgres, RustFS, and the API are down. That does not reopen the two source findings. REVIEW-ACCEPTED here covers this correction batch. JOURNEY-VERIFIED and RELEASED are not earned. No paid call.
