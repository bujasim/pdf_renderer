# PDF Viewer (PyWebView + Svelte + PDF.js)

This repo is in an **iterative build** process. The current behavior is:

- Centered layout
- Multipage scroll layout
- Fit-to-width on load
- Ctrl+Wheel smooth zoom preview
- Zoom settle re-render (reduces blur)
- Lazy render + cache visible pages
- Cursor-anchored zoom (falls back to center if cursor outside viewport)

## Structure
- `backend/` Python launcher (PyWebView)
- `frontend/` Svelte + Vite source
- `frontend/src/lib/PdfViewer.svelte` self-contained viewer component
- `web/` Vite build output (static assets loaded by PyWebView)

## Run (baseline)
1. `cd frontend`
2. `npm install`
3. `npm run build`
4. `cd ..`
5. `python backend/app.py`

## Current Baseline
- The viewer builds a multipage scroll stack and jumps to `pageNumber`.
- `Ctrl+Wheel` applies a CSS scale preview (layout scales via CSS variables).
- After ~140ms idle, visible pages re-render at the new scale.
- Cursor-anchored zoom accounts for centered pages; if the cursor is outside the viewport, zoom falls back to center.

## Component API (minimal)
- Props: `src` (URL), `pageNumber` (1-based), `pageMode` (`"all"` | `"subset"`), `pages` (array of page numbers)

## Optional Extensions (not implemented)
- Text layer for selection/CTRL+C.
- Overlay layer for bounding boxes/annotations.
