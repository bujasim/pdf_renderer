# PDF Viewer (PyWebView + Svelte + PDF.js)

This repo is in an **iterative build** process. The current snapshot is the last confirmed-good behavior:

- Centered layout
- Fit-to-width on load
- Ctrl+Wheel smooth zoom preview
- Zoom settle re-render (reduces blur)
- No cursor anchoring, no pan, no bounds logic yet

## Structure
- `backend/` Python launcher (PyWebView)
- `frontend/` Svelte + Vite source
- `web/` Vite build output (static assets loaded by PyWebView)

## Run (baseline)
1. `cd frontend`
2. `npm install`
3. `npm run build`
4. `cd ..`
5. `python backend/app.py`

## Current Baseline (Step 4)
- The viewer renders page 1 at fit-to-width scale.
- Ctrl+Wheel applies a CSS scale preview.
- After ~140ms idle, the page re-renders at the new scale.

## Next Steps
- Add cursor-anchored zoom without breaking the baseline.
- Add bounded pan after anchor is stable.
