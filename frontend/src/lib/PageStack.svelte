<script>
  export let stackEl;
  export let viewScale = 1;
  export let gap = 18;
  export let pad = 24;
</script>

<div
  class="page-stack"
  bind:this={stackEl}
  style={`--view-scale: ${viewScale}; --page-gap: ${gap}px; --page-pad: ${pad}px;`}
>
  <slot />
</div>

<style>
  .page-stack {
    --view-scale: 1;
    --page-gap: 18px;
    --page-pad: 24px;
    width: 100%;
    padding: calc(var(--page-pad) * var(--view-scale)) 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: calc(var(--page-gap) * var(--view-scale));
  }
</style>
