Qt PDF Based Rendering Architecture

Overview
This project now uses the Qt PDF module to handle all PDF loading, rendering, caching, tiling, and interaction. The custom PDFium worker, shared-memory buffers, and manual rendering pipeline have been removed in favor of the built-in Qt Quick PDF components.

Key Components (QML)
- PdfDocument: loads the PDF from a file URL, exposes metadata, status, and password handling.
- PdfScrollablePageView: provides a complete single-page viewer with scrolling, zooming, selection, links, and navigation.

Data Flow
- The UI sets PdfDocument.source to a file URL (typically from FileDialog).
- PdfScrollablePageView binds to the PdfDocument and renders the current page.
- Qt handles rendering, caching, and threaded work internally.

User-Facing Behavior
- Open a PDF via File dialog.
- Scroll normally with the mouse wheel or touchpad.
- Hold Ctrl and use the wheel/trackpad to zoom.
- Zoom via menu or built-in gestures.
- Fit-to-page or fit-to-width via menu.
- Navigate with back/forward history.

Notes
- PdfDocument.source requires a URL (file://) rather than a plain filesystem path.
- Password-protected PDFs are handled via PdfDocument.password and the passwordRequired signal.

Zoom Interaction Experiment Log (Qt PDF)
Goal: Achieve AutoCAD-like zooming that feels smooth and anchored, without white flashes or jitter.

Baseline
- Added Ctrl+wheel zoom in QML via WheelHandler; normal wheel should scroll.
- Initial issues: wheel zoom hijacked scroll, zoom only registered intermittently, or required releasing Ctrl between steps.

Wheel Handling Iterations
- Tried global WheelHandler with grab permissions to steal wheel events. Result: zoom became unreliable and scrolling was blocked.
- Moved wheel handling into the PdfScrollablePageView to avoid event contention. Result: scroll restored, but zoom still inconsistent.
- Simplified to acceptedModifiers=Ctrl and no grabbing: stable Ctrl+wheel zoom, normal scroll restored.

Smooth Zoom Attempts
- Implemented continuous zoom using wheel delta accumulation and exponential factor updates on a timer.
- Result: smoother input, but heavy rasterization cost caused low FPS and white flashes during active zoom.

Performance Mitigation Attempts
- Throttled updates and used bucketed zoom levels during interaction; settled to final scale after idle.
- Result: faster, but still white flashes (full rerender during interaction).

Preview Transform Strategy
- Replaced live renderScale updates with a view-level Scale transform during interaction (GPU scale preview).
- Result: eliminated most white flashes and improved responsiveness.
- Issue: on settle, the view jumped toward the top-left corner.

Anchor Preservation Attempts
- Tried to preserve the anchor by adjusting contentX/Y after setting renderScale.
- Issue persisted due to content size updates and view internals resetting scroll position.
- Switched to Qt navigation API: computed anchor in page coordinates and called goToLocation(page, location, zoom).
- Current status: still jumps toward top-left on settle in some cases; needs further investigation.

Known Issues (Current State)
- Settling after zoom interaction can jump to top-left.
- Smooth zoom remains constrained by PDFium raster cost; continuous rerendering is expensive.

Next Ideas (Future Work)
- Investigate whether PdfScrollablePageView exposes a stable anchor API for zooming.
- Explore rendering behavior differences in PdfMultiPageView vs PdfScrollablePageView.
- Consider a custom QML wrapper that tracks page-space anchor and applies goToLocation with measured page geometry.
- Add debug overlay for renderScale/contentX/contentY/location to validate anchor math.
