<script>
  import { tick } from "svelte";
  import { loadPdf, renderPage } from "./pdfjs";
  import FrameLayout from "./FrameLayout.svelte";
  import ScrollViewport from "./ScrollViewport.svelte";
  import PageStack from "./PageStack.svelte";

  export let src = "";
  export let pageNumber = 1;

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
  let loadToken = 0;
  let observer = null;
  const elementToState = new WeakMap();

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
    return Array.from({ length: count }, (_, index) => ({
      number: index + 1,
      el: null,
      canvasEl: null,
      page: null,
      baseWidth: defaultWidth,
      baseHeight: defaultHeight,
      renderedScale: 0,
      visible: false,
      rendering: false,
    }));
  }

  async function renderPageForState(state) {
    if (!pdfDoc || !state.canvasEl) return;
    if (state.renderedScale === renderScale || state.rendering) return;
    state.rendering = true;
    try {
      if (!state.page) state.page = await pdfDoc.getPage(state.number);
      const viewport = state.page.getViewport({ scale: renderScale });
      updatePageBase(state, viewport.width, viewport.height);
      await renderPage(state.page, renderScale, state.canvasEl);
      state.renderedScale = renderScale;
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

  function rescaleAllPageBases(ratio) {
    if (!ratio || ratio === 1) return;
    for (const state of pageStates) {
      updatePageBase(state, state.baseWidth * ratio, state.baseHeight * ratio);
      state.renderedScale = 0;
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
    clearSettle();
    emptyStateVisible = true;
  }

  function scrollToPage(targetPage) {
    const state = pageStates[targetPage - 1];
    if (!state || !state.el) return;
    state.el.scrollIntoView({ block: "start" });
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
    pageStates = createPageStates(doc.numPages, firstViewport.width, firstViewport.height);
    await tick();
    setupObserver();
    emptyStateVisible = false;
    await renderPageForState(pageStates[Math.max(0, pageNumber - 1)]);
    scrollToPage(pageNumber);
  }

  $: if (src !== lastSrc) {
    lastSrc = src;
    loadFromSource(src);
  }

  $: if (src && pageNumber !== lastPageNumber) {
    lastPageNumber = pageNumber;
    scrollToPage(pageNumber);
    const state = pageStates[pageNumber - 1];
    if (state) renderPageForState(state);
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
          <canvas class="pdf-canvas" bind:this={state.canvasEl}></canvas>
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

  .pdf-canvas {
    width: 100%;
    height: 100%;
    display: block;
    background: white;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  }
</style>
