<script>
  export let scrollEl;
  export let onWheel = null;

  function handleWheel(event) {
    if (onWheel) onWheel(event);
  }
</script>

<div class="scroll-viewport" bind:this={scrollEl} on:wheel={handleWheel}>
  <slot />
</div>

<style>
  .scroll-viewport {
    height: 100%;
    width: 100%;
    overflow: auto;
    overflow-anchor: none;
  }
</style>
