<script>
  import { onMount } from "svelte";
  import Toolbar from "./lib/Toolbar.svelte";
  import PdfViewer from "./lib/PdfViewer.svelte";

  let src = "";
  let pageNumber = 1;

  function handleOpen(event) {
    src = event.detail.url;
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
  <div class="viewer-shell">
    <PdfViewer {src} {pageNumber} />
  </div>
</div>
