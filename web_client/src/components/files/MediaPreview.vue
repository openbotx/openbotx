<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'

const props = defineProps({
  path: { type: String, default: '' },
  type: { type: String, default: '' },
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
  <div class="media-container">
    <div class="media-toolbar">
      <span class="media-path">{{ path }}</span>
      <div class="media-info">
        <span class="media-meta">{{ mime }} &middot; {{ formattedSize }}</span>
        <a :href="url" :download="filename">
          <Button label="Download" icon="pi pi-download" size="small" severity="secondary" />
        </a>
      </div>
    </div>

    <div class="media-preview">
      <img
        v-if="type === 'image'"
        :src="url"
        :alt="filename"
        class="preview-image"
      />
      <video
        v-else-if="type === 'video'"
        :src="url"
        controls
        class="preview-video"
      />
      <audio
        v-else-if="type === 'audio'"
        :src="url"
        controls
        class="preview-audio"
      />
    </div>
  </div>
</template>

<style scoped>
.media-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.media-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.media-path {
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
  overflow-wrap: break-word;
  word-break: break-all;
  min-width: 0;
}

.media-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.media-meta {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
}

.media-preview {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  overflow: auto;
  background: var(--p-surface-50);
}

:global(.dark-mode) .media-preview {
  background: var(--p-surface-900);
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 0.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.preview-video {
  max-width: 100%;
  max-height: 100%;
  border-radius: 0.5rem;
}

.preview-audio {
  width: 100%;
  max-width: 500px;
}

@media (max-width: 768px) {
  .media-toolbar {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.75rem;
  }

  .media-preview {
    padding: 1rem;
  }
}
</style>
