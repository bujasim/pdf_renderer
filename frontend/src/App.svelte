<script>
  import Toolbar from "./lib/Toolbar.svelte";
  import Viewer from "./lib/Viewer.svelte";

  let viewerRef;

  function handleOpen(event) {
    viewerRef?.openUrl(event.detail.url);
  }
</script>

<div class="app">
  <Toolbar on:open={handleOpen} />
  <Viewer bind:this={viewerRef} />
</div>
