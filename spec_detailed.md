# Detailed Specification: Interface-Agnostic Tiled PDF Renderer

This document expands `spec.md` with a concrete implementation plan to decouple the rendering core from the UI, enabling reuse across QML, CLI, or future C++/Rust frontends.

---

## 1. Goals

- **Interface agnostic core**: UI-agnostic renderer that accepts `(pdf_path, page_number, text)` and delivers tiles + metadata.
- **Strict thread ownership**: All PyMuPDF objects live in a single render thread.
- **Deterministic caching**: Stable cache keys derived from input tuple, zoom bucket, and tile coordinates.
- **Progressive rendering-ready**: Design supports preview/refine passes later without UI changes.

---

## 2. Architecture Overview

### 2.1 Core Modules

- `core/renderer.py` (new):
  - `TiledPdfRenderer` (interface-agnostic class).
  - Owns `DocumentManager`, `TileCache`, and `RenderWorker`.
  - Exposes `update_viewport(...)` and emits `tile_ready(...)` with metadata.

- `core/scheduler.py` (new):
  - Priority scheduling, generation handling, and queue management.

- `core/models.py` (new):
  - `RenderRequest` dataclass.
  - `TileResult` dataclass.

### 2.2 UI Adapter

- `ui/qml_controller.py` (rename from `main.py` logic):
  - Thin wrapper around `TiledPdfRenderer`.
  - QML-specific `Property` and `Signal` wiring.

---

## 3. Public API: TiledPdfRenderer

### 3.1 Constructor

```python
renderer = TiledPdfRenderer(tile_size=256, bucket_ratio=1.125, cache_bytes=100*1024*1024)
```

### 3.2 Input Tuple

The core uses a simple tuple, e.g.:

```python
doc_tuple = (pdf_path, page_number, text)
```

The `text` field is optional and reserved for future overlay logic or document-specific metadata. It does not affect rasterization yet.

### 3.3 Methods

```python
renderer.set_document(pdf_path, page_number, text=None)
renderer.update_viewport(x, y, w, h, zoom)
renderer.shutdown()
```

### 3.4 Signals / Callbacks

```python
tile_ready(
    key: str,
    row: int,
    col: int,
    zoom: float,
    image: QImage,
    generation_id: int,
    pass_type: str  # "preview" or "refine" (future)
)
```

**Note**: The signal can be implemented as Qt `Signal` or a plain Python callback list.

---

## 4. Cache Keys and Determinism

### 4.1 Key Format

```
<doc_id>_<page>_<bucket_zoom>_<row>_<col>_<pass_type>
```

### 4.2 doc_id

- Derived from `pdf_path` hash and document metadata (mtime, size).
- Allows detection of file updates.

---

## 5. Viewport Computation

### 5.1 Tile Grid

- Tile grid is defined in **page coordinates**.
- Tile size is constant in screen pixels (default 256).
- Page tile size in page-space = `tile_size / bucket_zoom`.

### 5.2 Clip Rects

MuPDF `clip` requires `(x0, y0, x1, y1)` in page coordinates.

### 5.3 Generation ID

- Each `update_viewport` increments `generation_id`.
- RenderWorker drops requests from stale generations.

---

## 6. Render Pipeline

1. UI calls `update_viewport`.
2. Scheduler computes tile rects.
3. RenderWorker renders via `page.get_pixmap(matrix=..., clip=...)`.
4. Pixmap converted to `QImage`.
5. Tile inserted into `TileCache`.
6. `tile_ready` emitted.

---

## 7. UI Integration Strategy

### 7.1 Option B (Current Path)

- Keep last valid tile in each slot until new tile arrives.
- Avoid flicker during zoom/pan.
- QML should not hard-clear tiles on zoom.

### 7.2 Option C (Future)

- Preview pass tiles shown immediately.
- Refine pass replaces them progressively.

---

## 8. Text Input Handling (Planned)

The third tuple element `text` is accepted but not yet used. Planned uses:

- **Overlay extraction**: interpret text as a query string and highlight matching spans.
- **Annotation alignment**: text as JSON payload describing overlays aligned to page coordinates.

Implementation for both should live outside core rendering and in a separate overlay pipeline.

---

## 9. Threading Model

- `DocumentManager` and all MuPDF objects owned by render thread.
- UI thread never touches PyMuPDF.
- RenderWorker uses a single Python thread + priority queue.

---

## 10. Testing Plan

1. Unit test `compute_tiles(...)` for coordinate correctness.
2. Render a fixed 1-page PDF, ensure tile cache sizes and keys match expectations.
3. Simulate zoom in/out and ensure generation cancellation works.

---

## 11. Migration Plan

1. Extract current rendering logic into `TiledPdfRenderer`.
2. Replace QML controller to call into the new core.
3. Keep existing QML tile layout, but wire to new callbacks.
4. Add preview/refine pass after stability.

