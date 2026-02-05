<script>
  import { onMount } from "svelte";
  import Toolbar from "./lib/Toolbar.svelte";
  import PdfViewer from "./lib/PdfViewer.svelte";

  let src = "";
  let pageNumber = 1;
  let pageMode = "all";
  let pagesInput = "1-3, 5";
  let pages = [];
  let renderText = false;
  let showOverlays = false;
  let overlays = [];
  let scrollToAnnotationId = "";

  const sampleOverlays = [
    { id: "a1", page: 1, x: 72, y: 72, width: 200, height: 60, color: "#ff7a00" },
    { id: "a2", page: 1, x: 72, y: 160, width: 300, height: 40, color: "#41d3bd" },
  ];

  function handleOpen(event) {
    src = event.detail.url;
  }

  function parsePages(text) {
    const tokens = String(text || "")
      .split(/[, ]+/)
      .map((token) => token.trim())
      .filter(Boolean);
    const values = new Set();
    for (const token of tokens) {
      if (token.includes("-")) {
        const [startRaw, endRaw] = token.split("-");
        const start = Number(startRaw);
        const end = Number(endRaw);
        if (!Number.isInteger(start) || !Number.isInteger(end)) continue;
        if (start > end) continue;
        for (let i = start; i <= end; i += 1) values.add(i);
      } else {
        const value = Number(token);
        if (!Number.isInteger(value)) continue;
        values.add(value);
      }
    }
    return Array.from(values).sort((a, b) => a - b);
  }

  $: if (pageMode === "subset") {
    pages = parsePages(pagesInput);
  } else {
    pages = [];
  }

  $: {
    overlays = showOverlays ? sampleOverlays : [];
  }

  function readQueryFile() {
    const params = new URLSearchParams(window.location.search);
    const file = params.get("file");
    if (file) src = file;
  }

  onMount(readQueryFile);
</script>

<div class="app">
  <Toolbar on:open={handleOpen} />
  <div class="debug-bar">
    <label class="debug-field">
      <span>Page</span>
      <input type="number" min="1" bind:value={pageNumber} />
    </label>
    <label class="debug-field debug-toggle">
      <input
        type="checkbox"
        checked={pageMode === "subset"}
        on:change={(event) => (pageMode = event.target.checked ? "subset" : "all")}
      />
      <span>Subset mode</span>
    </label>
    <label class="debug-field debug-toggle">
      <input
        type="checkbox"
        checked={renderText}
        on:change={(event) => (renderText = event.target.checked)}
      />
      <span>Text layer</span>
    </label>
    <label class="debug-field debug-toggle">
      <input
        type="checkbox"
        checked={showOverlays}
        on:change={(event) => (showOverlays = event.target.checked)}
      />
      <span>Overlays</span>
    </label>
    <label class="debug-field debug-pages">
      <span>Scroll to ID</span>
      <input type="text" bind:value={scrollToAnnotationId} placeholder="a1" />
    </label>
    {#if pageMode === "subset"}
      <label class="debug-field debug-pages">
        <span>Pages</span>
        <input type="text" bind:value={pagesInput} placeholder="1-3,5,10" />
      </label>
    {/if}
  </div>
  <div class="viewer-shell">
    <PdfViewer
      {src}
      {pageNumber}
      {pageMode}
      {pages}
      {renderText}
      {overlays}
      {scrollToAnnotationId}
    />
  </div>
</div>
