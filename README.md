# PDF Viewer (PyWebView + Svelte + PDF.js)

## Intent
- Self-contained Svelte component for embedding into a larger app.
- Performance-first: lazy render, caching, minimal DOM churn.
- Predictable UX: centered pages, fit-to-width on load, smooth zoom.

## Run (baseline)
1. `cd frontend`
2. `npm install`
3. `npm run build`
4. `cd ..`
5. `python backend/app.py`

## Component Usage
```svelte
<script>
  import PdfViewer from "./lib/PdfViewer.svelte";

  const overlays = [
    { id: "a1", page: 1, x: 72, y: 72, width: 200, height: 60, color: "#ff7a00" },
  ];
</script>

<PdfViewer
  src="/docs/sample.pdf"
  pageNumber={1}
  pageMode="all"
  renderText={true}
  overlays={overlays}
  scrollToAnnotationId={"a1"}
/>
```

## Props
- `src` (string, required)
  - PDF URL or file path.
- `pageNumber` (number, 1-based)
  - Scrolls to this page when set.
- `pageMode` (`"all" | "subset"`)
  - `"all"`: render all pages lazily.
  - `"subset"`: render only the pages in `pages`.
- `pages` (number[])
  - Used only when `pageMode="subset"`.
  - Invalid or missing page numbers are ignored.
- `renderText` (boolean)
  - Enables pdf.js text layer for selection and CTRL+C.
- `overlays` (array)
  - Bounding boxes drawn over pages.
- `scrollToAnnotationId` (string | number | null)
  - Scrolls to the overlay with matching `id` and centers it.
  - If the target page is not in the subset, it logs a warning and does nothing.
- `scrollToAnnotationZoom` (boolean)
  - When true, zooms in (if needed) so the target overlay fits comfortably in view.
- `debugScroll` (boolean)
  - When true, logs scroll math to the PyWebView log file (see Debugging).

## Behavior Notes
- Fit-to-width is computed on load using the first page and container width.
- `Ctrl+Wheel` zooms smoothly via CSS preview, then re-renders at the new scale.
- Zoom is cursor-anchored when the cursor is within the viewport.
- Pages are centered in the viewport.
- Lazy rendering uses `IntersectionObserver` with a large root margin.

## Overlays
- Coordinate system: PDF units with origin at bottom-left of the page.
- Required fields: `page`, `x`, `y`, `width`, `height`.
- Optional fields: `id`, `color`, `borderWidth`, `borderStyle`, `fill`.

Overlay shape example:
```js
{
  id: "case-41",
  page: 12,
  x: 144,
  y: 200,
  width: 120,
  height: 24,
  color: "rgba(255, 0, 0, 0.8)",
  borderWidth: 2,
  borderStyle: "solid",
  fill: "transparent"
}
```

## Debugging
- `debugScroll` writes JSON lines to `logs/scroll-debug.jsonl` via the PyWebView JS API.
- Enable it only when troubleshooting scroll/zoom behavior.

## Internal Design (overview)
- `PdfViewer.svelte` orchestrates loading, paging, zoom, and rendering.
- `FrameLayout.svelte` provides the centered layout shell.
- `ScrollViewport.svelte` handles scroll and wheel events.
- `PageStack.svelte` scales gaps/padding via `viewScale`.
- `pdfjs.js` wraps `pdfjs-dist` and exposes render helpers.
