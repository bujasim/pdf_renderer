import sys
import os
import ctypes
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable
from multiprocessing import Process, Queue, shared_memory
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtCore import QObject, Slot, Signal, Property, QThread, QTimer
import traceback
import queue
import logging
from logging_utils import CONSOLE_HANDLER

try:
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c
except ImportError:
    print("Error: pypdfium2 not installed. Run: pip install pypdfium2")
    sys.exit(1)


logger = logging.getLogger("pdf_renderer")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    logger.addHandler(CONSOLE_HANDLER)
logger.propagate = False

@dataclass
class RenderRequest:
    request_id: int
    pdf_path: str
    page_number: int
    center_x: float
    center_y: float
    scale: float
    render_scale: float
    viewport_width: int
    viewport_height: int
    buffer_name: str
    buffer_size: int
    stride: int
    dpr: float
    render_dpr: float
    created_ts: float

def render_worker_process(
    request_queue: Queue,
    result_queue: Queue
):
    """Renderer process that runs PDFium operations in isolation."""
    worker_logger = logging.getLogger("pdf_renderer.worker")
    worker_logger.setLevel(logging.DEBUG)
    if not worker_logger.handlers:
        worker_logger.addHandler(CONSOLE_HANDLER)
    worker_logger.propagate = False
    try:
        doc_cache = {}
        buffer_cache = {}
        worker_logger.debug("Worker process started")
        while True:
            request = request_queue.get()
            
            if request is None:
                worker_logger.debug("Worker process received shutdown signal")
                break
            
            req: RenderRequest = request
            start_ts = time.perf_counter()
            worker_logger.debug(
                "Render request id=%s pdf=%s page=%s scale=%.6f center=(%.3f,%.3f) viewport=(%sx%s)",
                req.request_id,
                req.pdf_path,
                req.page_number,
                req.scale,
                req.center_x,
                req.center_y,
                req.viewport_width,
                req.viewport_height,
            )
            
            try:
                if req.pdf_path not in doc_cache:
                    worker_logger.debug("Loading PDF document: %s", req.pdf_path)
                    doc_cache[req.pdf_path] = pdfium.PdfDocument(req.pdf_path)
                
                doc = doc_cache[req.pdf_path]
                page = doc[req.page_number]
                if req.buffer_name not in buffer_cache:
                    shm = shared_memory.SharedMemory(name=req.buffer_name)
                    buffer = (ctypes.c_ubyte * req.buffer_size).from_buffer(shm.buf)
                    buffer_cache[req.buffer_name] = (shm, buffer)
                    worker_logger.debug("Attached shared buffer name=%s size=%s", req.buffer_name, req.buffer_size)

                shm, buffer = buffer_cache[req.buffer_name]
                bitmap = pdfium.PdfBitmap.new_native(
                    req.viewport_width,
                    req.viewport_height,
                    pdfium_c.FPDFBitmap_BGRA,
                    buffer=buffer,
                    stride=req.stride,
                )
                bitmap.fill_rect((255, 255, 255, 255), 0, 0, req.viewport_width, req.viewport_height)

                matrix = pdfium_c.FS_MATRIX(
                    req.render_scale,
                    0.0,
                    0.0,
                    req.render_scale,
                    (req.viewport_width / 2.0) - (req.render_scale * req.center_x),
                    (req.viewport_height / 2.0) - (req.render_scale * req.center_y),
                )
                clip = pdfium_c.FS_RECTF(0.0, 0.0, float(req.viewport_width), float(req.viewport_height))

                render_start = time.perf_counter()
                pdfium_c.FPDF_RenderPageBitmapWithMatrix(
                    bitmap.raw,
                    page.raw,
                    ctypes.byref(matrix),
                    ctypes.byref(clip),
                    pdfium_c.FPDF_ANNOT,
                )
                render_ms = (time.perf_counter() - render_start) * 1000.0
                total_ms = (time.perf_counter() - start_ts) * 1000.0

                result_queue.put((
                    req.request_id,
                    req.buffer_name,
                    req.viewport_width,
                    req.viewport_height,
                    req.stride,
                    req.render_dpr,
                    req.created_ts,
                    render_ms,
                    total_ms,
                ))
                worker_logger.debug(
                    "Result queued id=%s buffer=%s size=(%s,%s) stride=%s render_ms=%.2f total_ms=%.2f",
                    req.request_id,
                    req.buffer_name,
                    req.viewport_width,
                    req.viewport_height,
                    req.stride,
                    render_ms,
                    total_ms,
                )
                
            except Exception as e:
                worker_logger.exception("Render error for id=%s", req.request_id)
                result_queue.put((
                    req.request_id,
                    None,
                    None,
                    None,
                    None,
                    None,
                    req.created_ts,
                    None,
                    None,
                ))
        
        for doc in doc_cache.values():
            doc.close()
        for shm, _ in buffer_cache.values():
            shm.close()
        worker_logger.debug("Worker process shutdown complete")
            
    except Exception as e:
        worker_logger.exception("Worker process error")

class FrameCache:
    def __init__(self):
        self._image: Optional[QImage] = None
        self._generation = 0

    def get(self) -> Optional[QImage]:
        if self._image is not None and not self._image.isNull():
            logger.debug("Frame cache hit gen=%s", self._generation)
            return self._image
        logger.debug("Frame cache miss")
        return None

    def set(self, image: QImage, generation: int) -> bool:
        if image is None or image.isNull():
            logger.debug("Frame cache set skipped gen=%s reason=null-image", generation)
            return False
        self._image = image
        self._generation = generation
        logger.debug("Frame cache updated gen=%s size=%s", generation, image.sizeInBytes())
        return True

class ViewportImageProvider(QQuickImageProvider):
    def __init__(self, cache: FrameCache):
        super().__init__(QQuickImageProvider.Image)
        self.cache = cache

    def requestImage(self, id: str, size, requestedSize):
        img = self.cache.get()
        if img:
            logger.debug("Image provider served frame")
            return img
        logger.debug("Image provider missing frame")
        return QImage()

class PDFController(QObject):
    pageChanged = Signal()
    frameReady = Signal(int)

    def __init__(self):
        super().__init__()
        self._pdf_path = ""
        self._page_number = 0
        self._page_width = 0.0
        self._page_height = 0.0

        self._center_x = 0.0
        self._center_y = 0.0
        self._scale = 1.0
        self._fit_scale = 1.0
        self._dpr = 1.0

        self._logical_width = 0.0
        self._logical_height = 0.0

        self._viewport_width = 0
        self._viewport_height = 0

        self._buffers_full = []
        self._buffer_views = {}
        self._buffer_stride = 0
        self._buffer_size = 0
        self._buffer_index = 0

        self.frame_cache = FrameCache()
        self.image_provider = ViewportImageProvider(self.frame_cache)

        self.request_queue = Queue()
        self.result_queue = Queue()

        self.worker_process = Process(
            target=render_worker_process,
            args=(self.request_queue, self.result_queue),
            daemon=True
        )
        self.worker_process.start()
        logger.debug("Worker process started pid=%s", self.worker_process.pid)

        self.result_thread = ResultThread(
            self.result_queue,
            self._get_buffer_view,
            self.frame_cache,
            self._accept_generation,
            self.frameReady,
        )
        self.result_thread.start()
        logger.debug("Result thread started")

        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_now)

        self._generation = 0
        self._latest_generation = 0
        self._inflight = False
        self._pending_render = False

        self.frameReady.connect(self._on_frame_ready)

    def _get_buffer_view(self, name: str) -> Optional[memoryview]:
        return self._buffer_views.get(name)

    def _accept_generation(self, generation: int) -> bool:
        return generation == self._latest_generation

    def _create_buffers(self, width: int, height: int):
        if width <= 0 or height <= 0:
            return
        if self._viewport_width == width and self._viewport_height == height and self._buffers_full:
            return

        for shm in self._buffers_full:
            try:
                shm.close()
                shm.unlink()
            except Exception:
                logger.debug("Shared buffer cleanup skipped")

        self._buffers_full = []
        self._buffer_views = {}
        self._buffer_stride = width * 4
        self._buffer_size = self._buffer_stride * height

        for idx in range(2):
            name = f"pdf_viewport_full_{os.getpid()}_{idx}_{width}x{height}"
            shm = shared_memory.SharedMemory(create=True, size=self._buffer_size, name=name)
            self._buffers_full.append(shm)
            self._buffer_views[name] = shm.buf
            logger.debug("Created shared buffer name=%s size=%s", name, self._buffer_size)

        self._buffer_index = 0

    def _screen_to_pdf(self, x_px: float, y_px: float) -> tuple[float, float]:
        if self._scale == 0:
            return (0.0, 0.0)
        pdf_x = self._center_x + (x_px - (self._viewport_width / 2.0)) / self._scale
        pdf_y = self._center_y + (y_px - (self._viewport_height / 2.0)) / self._scale
        return (pdf_x, pdf_y)

    def _set_center_from_anchor(self, pdf_x: float, pdf_y: float, anchor_x_px: float, anchor_y_px: float):
        self._center_x = pdf_x - (anchor_x_px - (self._viewport_width / 2.0)) / self._scale
        self._center_y = pdf_y - (anchor_y_px - (self._viewport_height / 2.0)) / self._scale

    @Property(str, notify=pageChanged)
    def pdfPath(self) -> str:
        return self._pdf_path

    @pdfPath.setter
    def pdfPath(self, value: str):
        if self._pdf_path != value:
            self._pdf_path = value
            logger.debug("PDF path set to %s", value)
            self._load_page_size()
            self.fitPage()
            self.pageChanged.emit()

    @Property(int, notify=pageChanged)
    def pageNumber(self) -> int:
        return self._page_number

    @pageNumber.setter
    def pageNumber(self, value: int):
        if self._page_number != value:
            self._page_number = value
            logger.debug("Page number set to %s", value)
            self._load_page_size()
            self.fitPage()
            self.pageChanged.emit()

    @Property(float, notify=pageChanged)
    def pageWidth(self) -> float:
        return self._page_width

    @Property(float, notify=pageChanged)
    def pageHeight(self) -> float:
        return self._page_height

    @Property(int, notify=frameReady)
    def frameId(self) -> int:
        return self._latest_generation

    @Property(float, notify=pageChanged)
    def zoomPercent(self) -> float:
        if self._fit_scale == 0:
            return 100.0
        return (self._scale / self._fit_scale) * 100.0

    def _load_page_size(self):
        if not self._pdf_path:
            return
        try:
            doc = pdfium.PdfDocument(self._pdf_path)
            page = doc[self._page_number]
            self._page_width = page.get_width()
            self._page_height = page.get_height()
            doc.close()
            logger.debug("Page size w=%s h=%s", self._page_width, self._page_height)
        except Exception:
            logger.exception("Failed to read page size")
            self._page_width = 0.0
            self._page_height = 0.0

    @Slot(float, float, float)
    def setViewportSize(self, width: float, height: float, dpr: float):
        self._dpr = max(1.0, dpr)
        self._logical_width = max(1.0, width)
        self._logical_height = max(1.0, height)
        self._viewport_width = int(self._logical_width * self._dpr)
        self._viewport_height = int(self._logical_height * self._dpr)
        logger.debug(
            "Viewport size set logical=(%s,%s) dpr=%.3f px=(%s,%s)",
            width,
            height,
            self._dpr,
            self._viewport_width,
            self._viewport_height,
        )
        self._create_buffers(self._viewport_width, self._viewport_height)
        self._schedule_render()

    @Slot()
    def fitPage(self):
        if not self._pdf_path or self._page_width <= 0 or self._page_height <= 0:
            return
        if self._viewport_width <= 0 or self._viewport_height <= 0:
            return
        scale_x = self._viewport_width / self._page_width
        scale_y = self._viewport_height / self._page_height
        self._fit_scale = min(scale_x, scale_y)
        self._scale = self._fit_scale
        self._center_x = self._page_width / 2.0
        self._center_y = self._page_height / 2.0
        logger.debug(
            "Fit page scale=%.6f center=(%.3f,%.3f)",
            self._scale,
            self._center_x,
            self._center_y,
        )
        self._schedule_render()

    @Slot(float, float)
    def panBy(self, dx: float, dy: float):
        if self._scale == 0:
            return
        dx_px = dx * self._dpr
        dy_px = dy * self._dpr
        self._center_x -= dx_px / self._scale
        self._center_y -= dy_px / self._scale
        logger.debug("Pan by dx=%.3f dy=%.3f -> center=(%.3f,%.3f)", dx, dy, self._center_x, self._center_y)
        self._schedule_render()

    @Slot(float, float, float)
    def zoomAt(self, factor: float, anchor_x: float, anchor_y: float):
        if factor <= 0 or self._scale == 0:
            return
        anchor_x_px = anchor_x * self._dpr
        anchor_y_px = anchor_y * self._dpr
        pdf_x, pdf_y = self._screen_to_pdf(anchor_x_px, anchor_y_px)
        self._scale *= factor
        self._set_center_from_anchor(pdf_x, pdf_y, anchor_x_px, anchor_y_px)
        logger.debug(
            "Zoom factor=%.4f scale=%.6f anchor=(%.1f,%.1f) center=(%.3f,%.3f)",
            factor,
            self._scale,
            anchor_x,
            anchor_y,
            self._center_x,
            self._center_y,
        )
        self._schedule_render()

    @Slot()
    def requestRender(self):
        self._schedule_render()

    def _schedule_render(self):
        if not self._pdf_path:
            logger.debug("Render skipped: empty pdf path")
            return
        if self._viewport_width <= 0 or self._viewport_height <= 0:
            logger.debug("Render skipped: invalid viewport size")
            return
        self._render_timer.start(33)

    def _render_now(self):
        if not self._buffers_full:
            return
        if self._inflight:
            self._pending_render = True
            return
        self._generation += 1
        self._latest_generation = self._generation

        buffer = self._buffers_full[self._buffer_index]
        self._buffer_index = (self._buffer_index + 1) % len(self._buffers_full)

        render_scale = self._scale
        req = RenderRequest(
            request_id=self._generation,
            pdf_path=self._pdf_path,
            page_number=self._page_number,
            center_x=self._center_x,
            center_y=self._center_y,
            scale=self._scale,
            render_scale=render_scale,
            viewport_width=self._viewport_width,
            viewport_height=self._viewport_height,
            buffer_name=buffer.name,
            buffer_size=self._buffer_size,
            stride=self._buffer_stride,
            dpr=self._dpr,
            render_dpr=self._dpr,
            created_ts=time.perf_counter(),
        )
        self._inflight = True
        self.request_queue.put(req)
        logger.debug("Render queued gen=%s buffer=%s scale=%.6f dpr=%.3f", self._generation, buffer.name, render_scale, self._dpr)

    def _on_frame_ready(self, generation: int):
        if generation != self._latest_generation:
            return
        self._inflight = False
        if self._pending_render:
            self._pending_render = False
            self._render_now()

    def shutdown(self):
        logger.debug("Shutdown initiated")
        self.request_queue.put(None)
        if self.result_thread.isRunning():
            self.result_thread.stop()
            self.result_thread.wait()
        if self.worker_process.is_alive():
            self.worker_process.join(timeout=1.0)
        for shm in self._buffers_full:
            try:
                shm.close()
                shm.unlink()
            except Exception:
                logger.debug("Shared buffer cleanup skipped")
        logger.debug("Shutdown complete")

class ResultThread(QThread):
    def __init__(
        self,
        result_queue: Queue,
        buffer_view_provider: Callable[[str], Optional[memoryview]],
        frame_cache: FrameCache,
        accept_generation: Callable[[int], bool],
        frame_ready_signal,
    ):
        super().__init__()
        self.result_queue = result_queue
        self.buffer_view_provider = buffer_view_provider
        self.frame_cache = frame_cache
        self.accept_generation = accept_generation
        self.frame_ready_signal = frame_ready_signal
        self._running = True

    def run(self):
        while self._running:
            try:
                result = self.result_queue.get(timeout=0.1)
                if result is None:
                    logger.debug("Result thread received shutdown signal")
                    break

                generation, buffer_name, width, height, stride, dpr, created_ts, render_ms, total_ms = result
                logger.debug(
                    "Result received gen=%s buffer=%s size=(%s,%s) stride=%s render_ms=%s total_ms=%s",
                    generation,
                    buffer_name,
                    width,
                    height,
                    stride,
                    None if render_ms is None else f"{render_ms:.2f}",
                    None if total_ms is None else f"{total_ms:.2f}",
                )

                if buffer_name is None:
                    continue

                if not self.accept_generation(generation):
                    logger.debug("Result dropped gen=%s (stale)", generation)
                    continue

                view = self.buffer_view_provider(buffer_name)
                if view is None:
                    logger.debug("Result skipped gen=%s (missing buffer)", generation)
                    continue

                img = QImage(
                    view,
                    width,
                    height,
                    stride,
                    QImage.Format_ARGB32
                )
                img.setDevicePixelRatio(dpr)
                if not img.isNull():
                    queue_ms = (time.perf_counter() - created_ts) * 1000.0
                    self.frame_cache.set(img, generation)
                    self.frame_ready_signal.emit(generation)
                    logger.debug("Frame ready emitted gen=%s queue_ms=%.2f", generation, queue_ms)

            except Exception as e:
                if isinstance(e, queue.Empty):
                    continue
                logger.exception("Result thread error")
                continue

    def stop(self):
        self._running = False

def main():
    import PySide6
    pyside_dir = Path(PySide6.__path__[0])
    
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(pyside_dir))
        plugins_dir = pyside_dir / "plugins"
        if plugins_dir.exists():
            os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
    logger.debug("Qt plugin path=%s", os.environ.get("QT_PLUGIN_PATH"))

    app = QGuiApplication(sys.argv)
    
    engine = QQmlApplicationEngine()
    
    qml_path = pyside_dir / "qml"
    if qml_path.exists():
        engine.addImportPath(str(qml_path))
    logger.debug("QML import path=%s", qml_path)
    
    controller = PDFController()
    engine.addImageProvider("pdf_viewport", controller.image_provider)
    engine.rootContext().setContextProperty("pdfController", controller)
    
    qml_file = Path(__file__).parent / "main.qml"
    engine.load(qml_file)
    logger.debug("QML loaded file=%s", qml_file)
    
    if not engine.rootObjects():
        controller.shutdown()
        sys.exit(-1)
    
    try:
        sys.exit(app.exec())
    finally:
        controller.shutdown()

if __name__ == "__main__":
    main()
