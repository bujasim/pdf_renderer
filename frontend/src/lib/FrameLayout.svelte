<script>
  export let frameEl;
  export let showEmpty = false;
  export let emptyTitle = "Drop a PDF or choose a file";
  export let emptySubtitle = "Provide a src path to render.";
</script>

<main class="frame" bind:this={frameEl} {...$$restProps}>
  <slot />
  {#if showEmpty}
    <div class="empty">
      <slot name="empty">
        <div class="empty-title">{emptyTitle}</div>
        <div class="empty-subtitle">{emptySubtitle}</div>
      </slot>
    </div>
  {/if}
</main>

<style>
  .frame {
    position: relative;
    height: 100%;
    width: 100%;
    overflow: hidden;
    display: block;
    background: radial-gradient(circle at top, rgba(65, 211, 189, 0.12), transparent 55%),
                radial-gradient(circle at bottom, rgba(120, 133, 255, 0.08), transparent 60%);
  }

  .empty {
    position: absolute;
    text-align: center;
    color: var(--muted, #9aa3b2);
    inset: 0;
    display: grid;
    place-content: center;
    pointer-events: none;
  }

  .empty-title {
    font-size: 20px;
    margin-bottom: 6px;
  }

  .empty-subtitle {
    font-size: 14px;
  }
</style>
