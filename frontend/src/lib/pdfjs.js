import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf";
import workerSrc from "pdfjs-dist/legacy/build/pdf.worker.min?url";

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

export async function loadPdf(url) {
  const task = pdfjsLib.getDocument(url);
  return task.promise;
}

export async function renderPage(page, scale, canvas) {
  const viewport = page.getViewport({ scale });
  const context = canvas.getContext("2d", { alpha: false });
  canvas.width = Math.floor(viewport.width);
  canvas.height = Math.floor(viewport.height);
  await page.render({ canvasContext: context, viewport }).promise;
}
