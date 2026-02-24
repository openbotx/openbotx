<script setup>
const props = defineProps({
  toolUse: { type: Object, default: null },
})
</script>

<template>
  <div v-if="toolUse" class="tool-indicator">
    <div class="tool-header">
      <i class="pi pi-spin pi-spinner"></i>
      <span class="tool-label">Using <strong>{{ toolUse.tool }}</strong></span>
    </div>
    <div v-if="toolUse.arguments" class="tool-args">
      {{ typeof toolUse.arguments === 'string' ? toolUse.arguments : JSON.stringify(toolUse.arguments).substring(0, 200) }}
    </div>
  </div>
</template>

<style scoped>
.tool-indicator {
  margin: 0.5rem 0;
  padding: 0.75rem;
  background: var(--p-surface-100);
  border-radius: 0.5rem;
  border-left: 3px solid var(--p-primary-color);
  font-size: 0.85rem;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--p-primary-color);
}

.tool-args {
  margin-top: 0.4rem;
  color: var(--p-text-muted-color);
  font-family: monospace;
  font-size: 0.8rem;
  word-break: break-all;
}
</style>
