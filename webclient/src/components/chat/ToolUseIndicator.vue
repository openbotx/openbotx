<script setup>
const props = defineProps({
  toolUse: { type: Object, default: null },
})
</script>

<template>
  <div v-if="toolUse" class="tool-indicator">
    <div class="tool-header">
      <i class="pi pi-spin pi-spinner"></i>
      <span class="tool-label">{{ toolUse.description || toolUse.tool }}</span>
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
</style>
