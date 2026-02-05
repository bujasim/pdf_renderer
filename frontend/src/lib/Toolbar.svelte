<script>
  import { createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher();

  function handleFilePick(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    dispatch("open", { url: URL.createObjectURL(file) });
  }
</script>

<header class="topbar">
  <div class="title">PDF Viewer</div>
  <div class="controls">
    <input type="file" accept="application/pdf" on:change={handleFilePick} />
    <span class="zoom-label">100%</span>
  </div>
</header>
