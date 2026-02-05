<script>
  import { tick } from "svelte";
  import { loadPdf, renderPage, renderTextLayer } from "./pdfjs";
  import FrameLayout from "./FrameLayout.svelte";
  import ScrollViewport from "./ScrollViewport.svelte";
  import PageStack from "./PageStack.svelte";

  export let src = "";
  export let pageNumber = 1;
  export let pageMode = "all"; // "all" | "subset"
  export let pages = [];
  export let renderText = false;
  export let overlays = [];
  export let scrollToAnnotationId = null;

  let scrollEl;

  let pdfDoc = null;
  let pageStates = [];
  let renderScale = 1.0;
  let viewScale = 1.0;
  let pageGap = 18;
  let pagePad = 24;
  let settleTimer = null;
  let emptyStateVisible = true;
  let lastSrc = "";
  let lastPageNumber = null;
  let lastPageMode = "all";
  let lastPagesKey = "";
  let lastOverlaysRef = overlays;
  let lastScrollToAnnotationId = scrollToAnnotationId;
  let loadToken = 0;
  let observer = null;
  const elementToState = new WeakMap();
  let pageStateByNumber = new Map();
  let basePageWidth = 0;
  let basePageHeight = 0;
  let overlaysByPage = new Map();
  let overlayById = new Map();
  let overlaysVersion = 0;

  const PAGE_GAP = 18;
  const PAGE_PAD = 24;
  const OBSERVER_MARGIN = "800px 0px";

  function clampTotalScale(next) {
    return Math.max(0.1, Math.min(10, next));
  }

  function computeFitWidthScale(firstPage) {
    if (!firstPage || !scrollEl) return 1.0;
    const baseViewport = firstPage.getViewport({ scale: 1.0 });
    const containerWidth = scrollEl.clientWidth;
    if (!containerWidth) return 1.0;
    return containerWidth / baseViewport.width;
  }

  function clearSettle() {
    if (settleTimer) clearTimeout(settleTimer);
    settleTimer = null;
  }

  function updatePageBase(state, width, height) {
    state.baseWidth = width;
    state.baseHeight = height;
    if (!state.el) return;
    state.el.style.setProperty("--page-base-w", `${width}px`);
    state.el.style.setProperty("--page-base-h", `${height}px`);
  }

  function createPageStates(count, defaultWidth, defaultHeight) {
    return count.map((pageNum) => ({
      number: pageNum,
      el: null,
      contentEl: null,
      canvasEl: null,
      textEl: null,
      textLayer: null,
      overlayEl: null,
      overlayVersion: -1,
      overlayRenderedScale: 0,
      page: null,
      baseWidth: defaultWidth,
      baseHeight: defaultHeight,
      renderedScale: 0,
      textRenderedScale: 0,
      visible: false,
      rendering: false,
    }));
  }

  async function renderPageForState(state) {
    if (!pdfDoc || !state.canvasEl) return;
    const needsCanvas = state.renderedScale !== renderScale;
    const needsText = renderText && state.textRenderedScale !== renderScale;
    const needsOverlay =
      state.overlayEl &&
      (state.overlayVersion !== overlaysVersion ||
        state.overlayRenderedScale !== renderScale);
    if ((!needsCanvas && !needsText && !needsOverlay) || state.rendering) return;
    state.rendering = true;
    try {
      if (!state.page) state.page = await pdfDoc.getPage(state.number);
      const viewport = state.page.getViewport({ scale: renderScale });
      updatePageBase(state, viewport.width, viewport.height);
      if (needsCanvas) {
        await renderPage(state.page, renderScale, state.canvasEl);
        state.renderedScale = renderScale;
      }
      if (renderText && state.textEl) {
        if (state.textLayer?.cancel) state.textLayer.cancel();
        state.textLayer = await renderTextLayer(state.page, renderScale, state.textEl);
        state.textRenderedScale = renderScale;
      } else if (!renderText && state.textEl) {
        state.textEl.textContent = "";
        state.textRenderedScale = 0;
      }
      if (needsOverlay) {
        renderOverlaysForState(state);
      }
    } finally {
      state.rendering = false;
    }
  }

  function handleIntersect(entries) {
    for (const entry of entries) {
      const state = elementToState.get(entry.target);
      if (!state) continue;
      state.visible = entry.isIntersecting;
      if (entry.isIntersecting) renderPageForState(state);
    }
  }

  function setupObserver() {
    if (observer) observer.disconnect();
    if (!scrollEl) return;
    observer = new IntersectionObserver(handleIntersect, {
      root: scrollEl,
      rootMargin: OBSERVER_MARGIN,
      threshold: 0.01,
    });
    for (const state of pageStates) {
      if (!state.el) continue;
      elementToState.set(state.el, state);
      observer.observe(state.el);
    }
  }

  function rebuildPageIndex() {
    pageStateByNumber = new Map();
    for (const state of pageStates) {
      pageStateByNumber.set(state.number, state);
    }
  }

  function rebuildOverlaysIndex() {
    overlaysByPage = new Map();
    overlayById = new Map();
    if (!Array.isArray(overlays)) return;
    for (const overlay of overlays) {
      if (!overlay) continue;
      const page = Number(overlay.page);
      if (!Number.isInteger(page)) continue;
      if (!overlaysByPage.has(page)) overlaysByPage.set(page, []);
      overlaysByPage.get(page).push(overlay);
      if (overlay.id !== undefined && overlay.id !== null) {
        overlayById.set(String(overlay.id), overlay);
      }
    }
  }

  function renderOverlaysForState(state) {
    if (!state.overlayEl || !state.page) return;
    const list = overlaysByPage.get(state.number) || [];
    if (
      state.overlayVersion === overlaysVersion &&
      state.overlayRenderedScale === renderScale
    ) {
      return;
    }
    state.overlayEl.textContent = "";
    if (!list.length) {
      state.overlayRenderedScale = renderScale;
      state.overlayVersion = overlaysVersion;
      return;
    }
    const viewport = state.page.getViewport({ scale: renderScale });
    for (const item of list) {
      const x = Number(item.x) || 0;
      const y = Number(item.y) || 0;
      const width = Number(item.width) || 0;
      const height = Number(item.height) || 0;
      const rect = viewport.convertToViewportRectangle([
        x,
        y,
        x + width,
        y + height,
      ]);
      const left = Math.min(rect[0], rect[2]);
      const top = Math.min(rect[1], rect[3]);
      const boxWidth = Math.abs(rect[0] - rect[2]);
      const boxHeight = Math.abs(rect[1] - rect[3]);
      const borderColor = item.color || "rgba(255, 0, 0, 0.8)";
      const borderStyle = item.borderStyle || item.border || "solid";
      const borderWidth = Number(item.borderWidth ?? 2);
      const fill = item.fill || "transparent";

      const box = document.createElement("div");
      box.className = "overlay-box";
      if (item.id !== undefined && item.id !== null) {
        box.dataset.annotationId = String(item.id);
      }
      box.style.left = `${left}px`;
      box.style.top = `${top}px`;
      box.style.width = `${boxWidth}px`;
      box.style.height = `${boxHeight}px`;
      box.style.border = `${borderWidth}px ${borderStyle} ${borderColor}`;
      box.style.background = fill;
      state.overlayEl.appendChild(box);
    }
    state.overlayRenderedScale = renderScale;
    state.overlayVersion = overlaysVersion;
  }

  function normalizePages(input, maxPages) {
    if (!Array.isArray(input)) return [];
    const unique = new Set();
    for (const value of input) {
      const num = Number(value);
      if (!Number.isInteger(num)) continue;
      if (num < 1 || num > maxPages) continue;
      unique.add(num);
    }
    return Array.from(unique).sort((a, b) => a - b);
  }

  function getPageList(doc) {
    if (pageMode === "subset") {
      return normalizePages(pages, doc.numPages);
    }
    return Array.from({ length: doc.numPages }, (_, index) => index + 1);
  }

  function warnMissingPage(targetPage) {
    console.warn(`PdfViewer: pageNumber ${targetPage} not found in subset pages.`);
  }

  function rescaleAllPageBases(ratio) {
    if (!ratio || ratio === 1) return;
    for (const state of pageStates) {
      updatePageBase(state, state.baseWidth * ratio, state.baseHeight * ratio);
      state.renderedScale = 0;
      state.textRenderedScale = 0;
      state.overlayRenderedScale = 0;
    }
    pageGap *= ratio;
    pagePad *= ratio;
  }

  async function renderVisiblePages() {
    for (const state of pageStates) {
      if (state.visible) await renderPageForState(state);
    }
  }

  function scheduleSettle() {
    clearSettle();
    settleTimer = setTimeout(async () => {
      if (!pdfDoc) return;
      const previousScale = renderScale;
      renderScale = clampTotalScale(renderScale * viewScale);
      viewScale = 1.0;
      rescaleAllPageBases(renderScale / previousScale);
      await renderVisiblePages();
    }, 140);
  }

  function handleWheel(event) {
    if (!event.ctrlKey || !pdfDoc) return;
    event.preventDefault();
    if (!scrollEl) return;
    const factor = Math.exp(-event.deltaY * 0.002);
    const nextTotal = clampTotalScale(renderScale * viewScale * factor);
    const nextViewScale = nextTotal / renderScale;
    const ratio = nextViewScale / viewScale;
    if (!ratio || ratio === 1) return;
    const rect = scrollEl.getBoundingClientRect();
    const inside =
      event.clientX >= rect.left &&
      event.clientX <= rect.right &&
      event.clientY >= rect.top &&
      event.clientY <= rect.bottom;
    const anchorX = inside ? event.clientX - rect.left : rect.width / 2;
    const anchorY = inside ? event.clientY - rect.top : rect.height / 2;
    let nextScrollLeft;
    let nextScrollTop;
    const pageEl = inside ? event.target?.closest?.(".page") : null;
    const state = pageEl ? elementToState.get(pageEl) : null;
    if (state && state.el) {
      const pageWidth = state.baseWidth * viewScale;
      const pageLeft = (scrollEl.clientWidth - pageWidth) / 2;
      const pageTop = state.el.offsetTop;
      const docX = (scrollEl.scrollLeft + anchorX - pageLeft) / viewScale;
      const docY = (scrollEl.scrollTop + anchorY - pageTop) / viewScale;
      const nextPageWidth = state.baseWidth * nextViewScale;
      const nextPageLeft = (scrollEl.clientWidth - nextPageWidth) / 2;
      const nextPageTop = pageTop * ratio;
      nextScrollLeft = docX * nextViewScale + nextPageLeft - anchorX;
      nextScrollTop = docY * nextViewScale + nextPageTop - anchorY;
    } else {
      nextScrollLeft = (scrollEl.scrollLeft + anchorX) * ratio - anchorX;
      nextScrollTop = (scrollEl.scrollTop + anchorY) * ratio - anchorY;
    }
    viewScale = nextViewScale;
    scrollEl.scrollLeft = nextScrollLeft;
    scrollEl.scrollTop = nextScrollTop;
    scheduleSettle();
  }

  function resetState() {
    if (observer) observer.disconnect();
    observer = null;
    pdfDoc = null;
    pageStates = [];
    renderScale = 1.0;
    viewScale = 1.0;
    pageGap = PAGE_GAP;
    pagePad = PAGE_PAD;
    pageStateByNumber = new Map();
    basePageWidth = 0;
    basePageHeight = 0;
    overlaysByPage = new Map();
    overlaysVersion = 0;
    clearSettle();
    emptyStateVisible = true;
  }

  function scrollToPage(targetPage) {
    const state = pageStateByNumber.get(targetPage);
    if (!state || !state.el) {
      if (pageMode === "subset") warnMissingPage(targetPage);
      return;
    }
    state.el.scrollIntoView({ block: "start" });
  }

  async function scrollToAnnotation(targetId) {
    if (!targetId) return;
    const key = String(targetId);
    const overlay = overlayById.get(key);
    if (!overlay) {
      console.warn(`PdfViewer: annotation id ${key} not found.`);
      return;
    }
    const page = Number(overlay.page);
    if (!Number.isInteger(page)) return;
    const state = pageStateByNumber.get(page);
    if (!state || !state.el) {
      if (pageMode === "subset") {
        console.warn(
          `PdfViewer: annotation id ${key} page ${page} not in subset pages.`
        );
      }
      return;
    }
    await renderPageForState(state);
    await tick();
    await new Promise((resolve) => requestAnimationFrame(resolve));
    const target = state.el.querySelector(`[data-annotation-id="${key}"]`);
    if (!target) {
      console.warn(`PdfViewer: annotation id ${key} not rendered.`);
      return;
    }
    target.scrollIntoView({ block: "center", inline: "center" });
  }

  async function rebuildPageStates() {
    if (!pdfDoc) return;
    const pageList = getPageList(pdfDoc);
    pageStates = createPageStates(pageList, basePageWidth, basePageHeight);
    await tick();
    rebuildPageIndex();
    setupObserver();
    emptyStateVisible = pageStates.length === 0;
    if (!pageStates.length) {
      console.warn("PdfViewer: no pages to render in subset mode.");
      return;
    }
    scrollToPage(pageNumber);
    const state = pageStateByNumber.get(pageNumber);
    if (state) renderPageForState(state);
  }

  async function loadFromSource(nextSrc) {
    if (!nextSrc) {
      resetState();
      return;
    }
    clearSettle();
    emptyStateVisible = true;
    const token = ++loadToken;
    const doc = await loadPdf(nextSrc);
    if (token !== loadToken) return;
    pdfDoc = doc;
    const firstPage = await pdfDoc.getPage(1);
    await tick();
    renderScale = computeFitWidthScale(firstPage);
    pageGap = PAGE_GAP * renderScale;
    pagePad = PAGE_PAD * renderScale;
    viewScale = 1.0;
    const firstViewport = firstPage.getViewport({ scale: renderScale });
    basePageWidth = firstViewport.width;
    basePageHeight = firstViewport.height;
    pageStates = createPageStates(getPageList(doc), basePageWidth, basePageHeight);
    await tick();
    rebuildPageIndex();
    rebuildOverlaysIndex();
    overlaysVersion += 1;
    setupObserver();
    emptyStateVisible = pageStates.length === 0;
    if (!pageStates.length) {
      console.warn("PdfViewer: no pages to render in subset mode.");
      return;
    }
    const initialState = pageStateByNumber.get(pageNumber) || pageStates[0];
    if (!pageStateByNumber.has(pageNumber) && pageMode === "subset") {
      warnMissingPage(pageNumber);
    }
    await renderPageForState(initialState);
    scrollToPage(pageNumber);
  }

  $: if (src !== lastSrc) {
    lastSrc = src;
    loadFromSource(src);
  }

  $: if (src && pageNumber !== lastPageNumber) {
    lastPageNumber = pageNumber;
    scrollToPage(pageNumber);
    const state = pageStateByNumber.get(pageNumber);
    if (state) renderPageForState(state);
  }

  let lastRenderText = renderText;
  $: if (renderText !== lastRenderText) {
    lastRenderText = renderText;
    if (renderText) {
      tick().then(renderVisiblePages);
    } else {
      for (const state of pageStates) {
        if (state.textLayer?.cancel) state.textLayer.cancel();
        if (state.textEl) state.textEl.textContent = "";
        state.textLayer = null;
        state.textRenderedScale = 0;
      }
    }
  }

  $: {
    const pagesKey = Array.isArray(pages) ? pages.join(",") : "";
    if (pageMode !== lastPageMode || pagesKey !== lastPagesKey) {
      lastPageMode = pageMode;
      lastPagesKey = pagesKey;
      rebuildPageStates();
    }
  }

  $: if (overlays !== lastOverlaysRef) {
    lastOverlaysRef = overlays;
    rebuildOverlaysIndex();
    overlaysVersion += 1;
    tick().then(renderVisiblePages);
  }

  $: if (scrollToAnnotationId !== lastScrollToAnnotationId) {
    lastScrollToAnnotationId = scrollToAnnotationId;
    scrollToAnnotation(scrollToAnnotationId);
  }
</script>

<FrameLayout
  showEmpty={emptyStateVisible}
  emptyTitle="No PDF loaded"
  emptySubtitle="Provide a src path to render."
>
  <ScrollViewport bind:scrollEl onWheel={handleWheel}>
    <PageStack {viewScale} gap={pageGap} pad={pagePad}>
      {#each pageStates as state (state.number)}
        <div
          class="page"
          bind:this={state.el}
          style={`--page-base-w: ${state.baseWidth}px; --page-base-h: ${state.baseHeight}px;`}
        >
          <div
            class="page-content"
            bind:this={state.contentEl}
            style={`transform: ${viewScale === 1 ? "none" : `scale(${viewScale})`};`}
          >
            <canvas class="pdf-canvas" bind:this={state.canvasEl}></canvas>
            {#if renderText}
              <div class="textLayer text-layer" bind:this={state.textEl}></div>
            {/if}
            <div class="overlay-layer" bind:this={state.overlayEl}></div>
          </div>
        </div>
      {/each}
    </PageStack>
  </ScrollViewport>
</FrameLayout>

<style>
  .page {
    --page-base-w: 640px;
    --page-base-h: 900px;
    width: calc(var(--page-base-w) * var(--view-scale));
    height: calc(var(--page-base-h) * var(--view-scale));
    position: relative;
    flex: 0 0 auto;
  }

  .page-content {
    width: var(--page-base-w);
    height: var(--page-base-h);
    transform-origin: top left;
    position: relative;
  }

  .pdf-canvas {
    width: 100%;
    height: 100%;
    display: block;
    background: white;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
    position: relative;
    z-index: 0;
    pointer-events: none;
  }

  .text-layer {
    position: absolute;
    inset: 0;
    z-index: 1;
  }

  .overlay-layer {
    position: absolute;
    inset: 0;
    z-index: 2;
    pointer-events: none;
  }

  .overlay-box {
    position: absolute;
    box-sizing: border-box;
  }

  :global(.textLayer) {
    position: absolute;
    text-align: initial;
    inset: 0;
    overflow: clip;
    opacity: 1;
    line-height: 1;
    -webkit-text-size-adjust: none;
    -moz-text-size-adjust: none;
    text-size-adjust: none;
    forced-color-adjust: none;
    transform-origin: 0 0;
    caret-color: CanvasText;
    z-index: 0;
    -webkit-user-select: text;
    -moz-user-select: text;
    user-select: text;
  }

  :global(.textLayer.highlighting) {
    touch-action: none;
  }

  :global(.textLayer :is(span, br)) {
    color: transparent;
    position: absolute;
    white-space: pre;
    cursor: text;
    transform-origin: 0% 0%;
  }

  :global(.textLayer > :not(.markedContent)),
  :global(.textLayer .markedContent span:not(.markedContent)) {
    z-index: 1;
  }

  :global(.textLayer span.markedContent) {
    top: 0;
    height: 0;
  }

  :global(.textLayer span[role="img"]) {
    -webkit-user-select: none;
    -moz-user-select: none;
    user-select: none;
    cursor: default;
  }

  :global(.textLayer .highlight) {
    --highlight-bg-color: rgb(180 0 170 / 0.25);
    --highlight-selected-bg-color: rgb(0 100 0 / 0.25);
    --highlight-backdrop-filter: none;
    --highlight-selected-backdrop-filter: none;
    margin: -1px;
    padding: 1px;
    background-color: var(--highlight-bg-color);
    -webkit-backdrop-filter: var(--highlight-backdrop-filter);
    backdrop-filter: var(--highlight-backdrop-filter);
    border-radius: 4px;
  }

  :global(.textLayer ::-moz-selection) {
    background: rgba(0, 0, 255, 0.25);
    background: rgba(0 0 255 / 0.25);
    background: color-mix(in srgb, AccentColor, transparent 75%);
  }

  :global(.textLayer ::selection) {
    background: rgba(0, 0, 255, 0.25);
    background: rgba(0 0 255 / 0.25);
    background: color-mix(in srgb, AccentColor, transparent 75%);
  }

  :global(.textLayer br::-moz-selection) {
    background: transparent;
  }

  :global(.textLayer br::selection) {
    background: transparent;
  }

  :global(.textLayer .endOfContent) {
    display: block;
    position: absolute;
    inset: 100% 0 0;
    z-index: 0;
    cursor: default;
    -webkit-user-select: none;
    -moz-user-select: none;
    user-select: none;
  }

  :global(.textLayer.selecting .endOfContent) {
    top: 0;
  }
</style>
