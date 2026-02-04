import fitz
import threading
import queue
import uuid
from dataclasses import dataclass
from typing import Optional, Dict
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool
from PySide6.QtGui import QImage

TILE_SIZE = 256

@dataclass
class RenderRequest:
    request_id: str
    pdf_path: str
    page_number: int
    zoom: float
    tile_rect: tuple  # (x, y, w, h) in page coordinates
    generation_id: int
    tile_coords: tuple # (row, col) - for identification

class DocumentManager:
    """LRU cache for open MuPDF documents."""
    def __init__(self, cache_size=5):
        self.cache: Dict[str, fitz.Document] = {}
        self.access_order = []
        self.cache_size = cache_size
        self.lock = threading.Lock()

    def get_document(self, path: str) -> fitz.Document:
        with self.lock:
            if path in self.cache:
                self.access_order.remove(path)
                self.access_order.append(path)
                return self.cache[path]
            
            doc = fitz.open(path)
            if len(self.cache) >= self.cache_size:
                oldest = self.access_order.pop(0)
                self.cache[oldest].close()
                del self.cache[oldest]
            
            self.cache[path] = doc
            self.access_order.append(path)
            return doc

class TileCache:
    """Simple bytes-bounded LRU cache for QImages."""
    def __init__(self, max_bytes=100 * 1024 * 1024): # 100MB default
        self.cache: Dict[str, QImage] = {}
        self.access_order = []
        self.max_bytes = max_bytes
        self.current_bytes = 0
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[QImage]:
        with self.lock:
            if key in self.cache:
                self.access_order.remove(key)
                self.access_order.append(key)
                return self.cache[key]
            return None

    def put(self, key, image) -> bool:
        with self.lock:
            if image is None or image.isNull():
                return False
            img_size = image.sizeInBytes()
            if key in self.cache:
                self.current_bytes -= self.cache[key].sizeInBytes()
                self.access_order.remove(key)
            
            while self.current_bytes + img_size > self.max_bytes and self.access_order:
                oldest_key = self.access_order.pop(0)
                self.current_bytes -= self.cache[oldest_key].sizeInBytes()
                del self.cache[oldest_key]
            
            self.cache[key] = image
            self.access_order.append(key)
            self.current_bytes += img_size
            return True

class RenderWorker(QObject):
    """Single thread that handles all MuPDF rendering calls."""
    tile_rendered = Signal(str, int, int, float, QImage, int, tuple) # req_id, x, y, zoom, image, gen_id, coords

    def __init__(self, doc_manager: DocumentManager):
        super().__init__()
        self.doc_manager = doc_manager
        self.request_queue = queue.PriorityQueue()
        self.request_count = 0  # Counter for tie-breaking in priority queue
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.current_generation = 0

    def start(self):
        self.thread.start()

    def request_tile(self, request: RenderRequest, priority: int = 10):
        # Priority: lower is higher. 0 = immediate, 10 = default
        self.request_count += 1
        self.request_queue.put((priority, self.request_count, request))

    def _run(self):
        while not self._stop_event.is_set():
            try:
                priority, count, req = self.request_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Check cancellation
            if req.generation_id < self.current_generation:
                continue

            try:
                doc = self.doc_manager.get_document(req.pdf_path)
                page = doc.load_page(req.page_number)
                
                # Calculate matrix for zoom
                mat = fitz.Matrix(req.zoom, req.zoom)
                
                # Clip rect is in page coordinates
                # We need to map it to the scaled pixmap
                pix = page.get_pixmap(matrix=mat, clip=req.tile_rect)
                # Normalize to RGB/RGBA to avoid incompatible color spaces (e.g., CMYK)
                if pix.alpha:
                    pix = fitz.Pixmap(fitz.csRGBA, pix)
                else:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                
                # Convert to QImage
                fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
                if img.isNull():
                    # Fallback: go through PNG bytes for robust conversion
                    png_bytes = pix.tobytes("png")
                    img = QImage.fromData(png_bytes, "PNG")

                # Copy the image because the pixmap buffer will be destroyed
                img_copy = img.copy()
                
                self.tile_rendered.emit(
                    req.request_id,
                    req.tile_rect[0],
                    req.tile_rect[1],
                    req.zoom,
                    img_copy,
                    req.generation_id,
                    req.tile_coords
                )
            except Exception as e:
                print(f"Render error: {e}")
            finally:
                self.request_queue.task_done()
