<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'

const props = defineProps({
  path: { type: String, default: '' },
  mime: { type: String, default: '' },
  size: { type: Number, default: 0 },
  url: { type: String, default: '' },
})

const filename = computed(() => props.path.split('/').pop())

const formattedSize = computed(() => {
  const bytes = props.size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
})
</script>

<template>
  <div class="download-container">
    <div class="download-toolbar">
      <span class="download-path">{{ path }}</span>
    </div>

    <div class="download-body">
      <div class="download-card">
        <i class="pi pi-file" style="font-size: 3rem; color: var(--p-text-muted-color)"></i>
        <h3 class="download-filename">{{ filename }}</h3>
        <p class="download-meta">{{ mime || 'Unknown type' }} &middot; {{ formattedSize }}</p>
        <a :href="url" :download="filename">
          <Button label="Download" icon="pi pi-download" />
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.download-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.download-toolbar {
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.download-path {
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
  overflow-wrap: break-word;
  word-break: break-all;
}

.download-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.download-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
}

.download-filename {
  margin: 0;
  font-size: 1.1rem;
  overflow-wrap: break-word;
  word-break: break-all;
  text-align: center;
}

.download-meta {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}
</style>
