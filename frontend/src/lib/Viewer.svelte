<script>
  import { onMount, tick } from "svelte";
  import { loadPdf, renderPage } from "./pdfjs";

  let canvas;
  let viewportEl;
  let emptyStateVisible = true;

  let pdfDoc = null;
  let page = null;
  let renderScale = 1.0;
  let viewScale = 1.0;
  let settleTimer = null;

  function computeFitWidthScale() {
    if (!page || !viewportEl) return 1.0;
    const baseViewport = page.getViewport({ scale: 1.0 });
    const containerWidth = viewportEl.clientWidth;
    if (!containerWidth) return 1.0;
    return containerWidth / baseViewport.width;
  }

  async function renderFitWidth() {
    renderScale = computeFitWidthScale();
    viewScale = 1.0;
    await renderPage(page, renderScale, canvas);
    applyViewScale();
  }

  function applyViewScale() {
    if (!canvas) return;
    canvas.style.transform = `scale(${viewScale})`;
  }

  function clampTotalScale(next) {
    return Math.max(0.1, Math.min(10, next));
  }

  function scheduleSettle() {
    if (settleTimer) clearTimeout(settleTimer);
    settleTimer = setTimeout(async () => {
      if (!page) return;
      renderScale = clampTotalScale(renderScale * viewScale);
      viewScale = 1.0;
      await renderPage(page, renderScale, canvas);
      applyViewScale();
    }, 140);
  }

  function handleWheel(event) {
    if (!event.ctrlKey) return;
    event.preventDefault();
    const factor = Math.exp(-event.deltaY * 0.002);
    const nextTotal = clampTotalScale(renderScale * viewScale * factor);
    viewScale = nextTotal / renderScale;
    applyViewScale();
    scheduleSettle();
  }

  async function loadFromUrl(url) {
    if (!url) return;
    pdfDoc = await loadPdf(url);
    page = await pdfDoc.getPage(1);
    await tick();
    await renderFitWidth();
    emptyStateVisible = false;
  }

  export function openUrl(url) {
    loadFromUrl(url);
  }

  function handleDrop(event) {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (!file) return;
    loadFromUrl(URL.createObjectURL(file));
  }

  function readQueryFile() {
    const params = new URLSearchParams(window.location.search);
    const file = params.get("file");
    if (file) loadFromUrl(file);
  }

  onMount(() => {
    readQueryFile();
  });
</script>

<main
  class="viewport"
  bind:this={viewportEl}
  on:wheel={handleWheel}
  on:dragover|preventDefault
  on:drop={handleDrop}
>
  {#if emptyStateVisible}
    <div class="empty">
      <div class="empty-title">Drop a PDF or choose a file</div>
      <div class="empty-subtitle">Centered layout with smooth zoom preview and settle.</div>
    </div>
  {/if}
  <canvas bind:this={canvas}></canvas>
</main>
