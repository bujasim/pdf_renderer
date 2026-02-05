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
