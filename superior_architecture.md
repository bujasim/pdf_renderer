High-Performance PDF Rendering Architecture

Overview
This document describes the current architecture and rationale for the PDF viewport implementation in this repo. The goal is a reusable viewport widget that fits a PDF page by default, supports CAD-style pan/zoom, and renders as fast as possible without blocking the UI.

Engine Selection
- PDFium is used via pypdfium2 because it is permissively licensed and battle-tested.
- MuPDF is faster in benchmarks but is AGPL, which is unsuitable for a distributable library without a commercial license.

Current Implementation (Code State)
- Rendering is isolated in a single worker process using multiprocessing. This avoids PDFium thread-safety issues.
- The main process owns UI state, camera state, and shared memory buffers.
- The renderer uses matrix-based rendering (FPDF_RenderPageBitmapWithMatrix) to map PDF coordinates to viewport pixels.
- The output buffer is BGRA and is displayed with QImage.Format_ARGB32 for zero-copy rendering.
- Rendering is full-frame only (no tiling). Preview rendering was removed due to insufficient performance gains.
- Fit-to-page is the default behavior on load or page change.

Viewport Model (Camera)
- The PDF page is treated as a fixed world in PDF units.
- The viewport is a camera defined by:
  - center (cx, cy) in PDF units
  - scale in pixels per PDF unit
  - viewport size in device pixels (includes DPR)
- Pan adjusts the camera center. Zoom adjusts the scale around an anchor point so the anchor remains stable in screen space.

Transform Details
- Matrix form (a, b, c, d, e, f) maps PDF space to device pixels.
- Current mapping uses a positive Y scale and a translation that centers the camera in viewport coordinates.
- Rendering uses a clip rect matching the viewport bounds.

Data Flow
- UI requests render via a queue with a small request payload (camera state + buffer metadata).
- The worker process attaches to shared memory, renders into the buffer, and posts a lightweight completion message.
- The UI thread builds a QImage from shared memory and swaps the displayed frame.

Concurrency Model
- One worker process for PDFium rendering.
- The UI thread does not block on rendering.
- Render requests are coalesced: if a render is in-flight, only the latest pending request is kept.

Observability
- Logging includes render timings measured in the worker:
  - render_ms: time spent in PDFium render
  - total_ms: worker-side request handling
- UI logs include queue_ms: end-to-end latency from request to frame ready.

Known Performance Characteristics
- PDFium render time is the dominant cost (~100-120ms per full frame at 1536x1035 on DPR 1.5).
- Queue and shared memory overhead is minimal relative to render time.

User-Facing API (Current)
- load document: set pdfPath
- fit page: fitPage()
- pan: panBy(dx, dy)
- zoom with anchor: zoomAt(factor, x, y)
- request render: requestRender()

UI Integration (Current)
- QML uses a single Image backed by a QQuickImageProvider.
- Mouse drag pans the camera.
- Wheel and pinch zoom around the cursor/centroid.
- Fit page is available via menu.

Design Principles
- Separate camera state from rendering.
- Use process isolation for PDFium.
- Prefer zero-copy paths for pixel buffers.
- Keep the surface area small and predictable for drop-in usage.
