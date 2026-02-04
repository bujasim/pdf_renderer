# Specification: MuPDF Progressive Tiled PDF Viewer

A high-performance PDF viewer optimized for vector-heavy documents (e.g., CAD) using MuPDF and a progressive tiled rendering strategy.

## 1. Overview
The viewer aims to provide immediate visual feedback ("page visible ASAP") and smooth interaction on complex documents by decoupling document processing from UI rendering and using a multi-stage tiled approach.

*   **Inputs:** `pdf_path`, `page_number`.
*   **Core Goal:** Smooth pan/zoom with progressive refinement.

---

## 2. Rendering Model: Tiles & Progressive Passes
Everything on screen is rendered as a bitmap. The viewer does not display live vectors directly.

### Tile Grid
*   **Tile Size:** Configurable (default: 256 or 512 px).
*   **Viewport Logic:** Requests only tiles that intersect the visible area, plus an optional margin for prefetch.

### Progressive Refinement
On each viewport change (pan/zoom):
1.  **Preview Pass:** Fills the screen immediately using tiles from the nearest cached zoom bucket or a lower-resolution render.
2.  **Refine Pass:** Renders sharper tiles matching the current zoom level.
3.  **Settle Pass (Optional):** Once interaction stops (e.g., 150ms debounce), renders tiles at the exact scale for maximum crispness.

---

## 3. Threading & Process Model (v1: Qt + PyMuPDF)
To ensure UI responsiveness and adhere to MuPDF/PyMuPDF threading constraints, a strict separation of concerns is maintained.

### UI Thread (Qt Main Thread)
*   Manages viewport state (pan, zoom, rotation).
*   Handles tile placement, composition, and user input.
*   **Constraint:** Never calls PyMuPDF directly.

### Render Thread (Single Worker)
*   Owns all PyMuPDF objects (`Document`, `Page`).
*   Processes a priority queue of tile requests.
*   Checks a `generation_id` before each tile render to support immediate cancellation of obsolete work.
*   Emits rendered tiles (bitmaps) back to the UI thread via signals.

---

## 4. Core Runtime Components

### DocumentManager (LRU Cache)
*   Manages open document handles to avoid the overhead of repeated opening/parsing.
*   Key: `(path, mtime, size)`.

### DisplayListCache (Per Document)
*   Caches MuPDF **Display Lists** for active pages.
*   *Why:* Creating a display list is a one-time document-thread operation. Once created, multiple tiles can be rendered from it very quickly.

### RenderScheduler
*   Maintains a priority queue for tile requests:
    1.  Tiles currently visible in viewport.
    2.  Tiles near the viewport center.
    3.  Tiles in the prefetch margin.
*   Implements **Cancellation**: Each new viewport state increments a `generation_id`. The worker aborts rendering if the request ID is no longer current.

### TileCache (Global LRU)
*   Bytes-bounded cache for rendered tile bitmaps.
*   Key components: `doc_id`, `page_number`, `zoom_bucket_id`, `tile_x`, `tile_y`, `rotation`, and `pass_type`.

---

## 5. Zoom & Viewport Strategy

### Logarithmic Zoom Buckets
To maximize cache reuse and prevent "thrashing" during continuous zoom gestures, zoom levels are grouped into buckets.
*   **Ratio (`r`):** Typically 1.125 (12.5% steps).
*   **Formula:** `bucket_id = round(log(zoom / base_zoom) / log(r))`.

### Hysteresis
A small margin (e.g., 3-5%) is applied to bucket boundaries. The viewer only switches zoom buckets when the zoom level moves significantly beyond the current bucket's range, preventing flickering during small adjustments.

### UI Zoom & Tile Stability (v1)
To avoid visible flicker during zoom/pan, the UI keeps previously rendered tiles visible until new tiles are ready:
*   Each tile slot holds the last ready cache key (`lastKey`).
*   On zoom changes, the UI continues to display the previous tiles (scaled by QML) until the renderer emits `tileReady` for the current bucket.
*   No hard invalidation on zoom; tiles are replaced only when a newer bucket tile arrives.

---

## 6. Implementation Details

### PyMuPDF Integration
*   **Tiled Rendering:** Uses `page.get_pixmap(matrix=..., clip=...)`. The `clip` parameter is critical as it instructs MuPDF to only process the specific region of the page required for the tile.

### UI Composition
*   **Level 1 (CPU):** Convert pixmap buffers to `QImage` and draw them in the widget's `paintEvent`.
*   **Level 2 (GPU):** Upload tiles as textures to the GPU and render them as quads. This provides significantly smoother performance during high-speed panning and zooming.

---

## 7. Future Migration Path
*   **Backend:** The architecture is designed to allow replacing the Python/PyMuPDF render thread with a high-performance C++ or Rust implementation (using MuPDF's C API) without modifying the UI logic.
*   **Parallelism:** If a single render thread becomes a bottleneck, the system can transition to MuPDF's recommended multi-threaded model: one thread for document/display-list creation and multiple worker threads for rendering tiles from those display lists.
*   **Licensing:** Note that PyMuPDF is dual-licensed (AGPL/Commercial).
