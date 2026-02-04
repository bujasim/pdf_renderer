import sys
import os
from pathlib import Path
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtCore import QObject, Slot, Signal, Property, QRectF
import renderer

class TileImageProvider(QQuickImageProvider):
    def __init__(self, cache):
        super().__init__(QQuickImageProvider.Image)
        self.cache = cache

    def requestImage(self, id, size, requestedSize):
        # Strip query string if present
        clean_id = id.split('?')[0]
        img = self.cache.get(clean_id)
        if img:
            return img
        return QImage()

import math

import hashlib

class PDFController(QObject):
    pageChanged = Signal()
    viewportChanged = Signal()
    tileReady = Signal(str, int, int, float) # key, row, col, zoom

    def __init__(self):
        super().__init__()
        self._pdf_path = ""
        self._page_number = 0
        self._zoom = 1.0
        self._bucket_ratio = 1.125
        
        self.doc_manager = renderer.DocumentManager()
        self.tile_cache = renderer.TileCache()
        self.worker = renderer.RenderWorker(self.doc_manager)
        self.worker.tile_rendered.connect(self._on_tile_rendered)
        self.worker.start()
        
        self.image_provider = TileImageProvider(self.tile_cache)

    def _get_path_hash(self):
        return hashlib.md5(self._pdf_path.encode('utf-8')).hexdigest()[:8]

    @Property(str, notify=pageChanged)
    def pdfPath(self): return self._pdf_path
    @pdfPath.setter
    def pdfPath(self, v):
        if self._pdf_path != v:
            self._pdf_path = v
            self.pageChanged.emit()

    @Property(int, notify=pageChanged)
    def pageNumber(self): return self._page_number
    @pageNumber.setter
    def pageNumber(self, v):
        if self._page_number != v:
            self._page_number = v
            self.pageChanged.emit()

    @Property(float, notify=pageChanged)
    def pageWidth(self):
        if not self._pdf_path: return 0.0
        try:
            doc = self.doc_manager.get_document(self._pdf_path)
            page = doc.load_page(self._page_number)
            return page.rect.width
        except: return 0.0

    @Property(float, notify=pageChanged)
    def pageHeight(self):
        if not self._pdf_path: return 0.0
        try:
            doc = self.doc_manager.get_document(self._pdf_path)
            page = doc.load_page(self._page_number)
            return page.rect.height
        except: return 0.0

    @Property(int, notify=pageChanged)
    def tileWidth(self): return renderer.TILE_SIZE

    @Property(int, notify=pageChanged)
    def tileHeight(self): return renderer.TILE_SIZE

    def _get_bucket_zoom(self, zoom):
        if zoom <= 0: return 1.0
        bucket_id = round(math.log(zoom) / math.log(self._bucket_ratio))
        return self._bucket_ratio ** bucket_id

    @Slot(float, result=float)
    def getBucketZoom(self, zoom):
        return self._get_bucket_zoom(zoom)

    @Slot(float, float, float, float, float)
    def updateViewport(self, x, y, w, h, zoom):
        if not self._pdf_path: return

        self._zoom = zoom
        bucket_zoom = self._get_bucket_zoom(zoom)
        self.worker.current_generation += 1
        gen_id = self.worker.current_generation

        # Get page dimensions to bound tiles
        try:
            doc = self.doc_manager.get_document(self._pdf_path)
            page = doc.load_page(self._page_number)
            page_rect = page.rect
            page_w, page_h = page_rect.width, page_rect.height
        except Exception as e:
            print(f"Error loading page info: {e}")
            return

        # Tile size in page coordinates at current bucket_zoom
        tile_pw = renderer.TILE_SIZE / bucket_zoom
        tile_ph = renderer.TILE_SIZE / bucket_zoom

        # Visible range in page coordinates
        start_px = x / zoom
        start_py = y / zoom
        end_px = (x + w) / zoom
        end_py = (y + h) / zoom

        # Round to tile grid
        start_col = int(math.floor(start_px / tile_pw))
        start_row = int(math.floor(start_py / tile_ph))
        end_col = int(math.ceil(end_px / tile_pw))
        end_row = int(math.ceil(end_py / tile_ph))

        # Request tiles
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                # Calculate tile rect in page coordinates
                tx = col * tile_pw
                ty = row * tile_ph
                tw = tile_pw
                th = tile_ph

                # Intersect with page rect
                if tx >= page_w or ty >= page_h or tx + tw <= 0 or ty + th <= 0:
                    continue
                
                # Clip to page boundaries
                real_tx = max(0, tx)
                real_ty = max(0, ty)
                real_tw = min(page_w, tx + tw) - real_tx
                real_th = min(page_h, ty + th) - real_ty

                if real_tw <= 0 or real_th <= 0:
                    continue

                path_id = self._get_path_hash()
                cache_key = f"{path_id}_{self._page_number}_{bucket_zoom:.4f}_{row}_{col}"
                
                if self.tile_cache.get(cache_key):
                    self.tileReady.emit(cache_key, row, col, bucket_zoom)
                    continue

                # MuPDF expects clip rect as (x0, y0, x1, y1), not (x, y, w, h)
                clip_rect = (real_tx, real_ty, real_tx + real_tw, real_ty + real_th)

                req = renderer.RenderRequest(
                    request_id=cache_key,
                    pdf_path=self._pdf_path,
                    page_number=self._page_number,
                    zoom=bucket_zoom,
                    tile_rect=clip_rect,
                    generation_id=gen_id,
                    tile_coords=(row, col)
                )
                
                # Prioritize center tiles (simplified: lower priority number for center)
                mid_row = (start_row + end_row) / 2
                mid_col = (start_col + end_col) / 2
                dist = abs(row - mid_row) + abs(col - mid_col)
                self.worker.request_tile(req, priority=int(dist))

    def _on_tile_rendered(self, req_id, x, y, zoom, image, gen_id, coords):
        if self.tile_cache.put(req_id, image):
            self.tileReady.emit(req_id, coords[0], coords[1], zoom)

def main():
    import PySide6
    pyside_dir = Path(PySide6.__path__[0])
    
    # Fix for DLL loading on Windows (Python 3.8+)
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(pyside_dir))
        # Some Qt plugins are in 'plugins'
        plugins_dir = pyside_dir / "plugins"
        if plugins_dir.exists():
            os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)

    app = QGuiApplication(sys.argv)
    
    engine = QQmlApplicationEngine()
    
    # Add QML import path
    qml_path = pyside_dir / "qml"
    if qml_path.exists():
        engine.addImportPath(str(qml_path))
    
    controller = PDFController()
    engine.addImageProvider("pdf_tiles", controller.image_provider)
    engine.rootContext().setContextProperty("pdfController", controller)
    
    qml_file = Path(__file__).parent / "main.qml"
    engine.load(qml_file)
    
    if not engine.rootObjects():
        sys.exit(-1)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
