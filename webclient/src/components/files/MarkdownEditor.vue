<script setup>
import { ref, watch } from 'vue'
import { marked } from 'marked'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'

const props = defineProps({
  content: { type: String, default: '' },
  path: { type: String, default: '' },
})

const emit = defineEmits(['save'])
const editContent = ref(props.content)
const preview = ref(false)

watch(() => props.content, (val) => {
  editContent.value = val
})

function save() {
  emit('save', editContent.value)
}

function renderedHtml() {
  return marked(editContent.value || '', { breaks: true })
}
</script>

<template>
  <div class="editor-container">
    <div class="editor-toolbar">
      <span class="editor-path">{{ path }}</span>
      <div class="editor-actions">
        <Button
          :label="preview ? 'Edit' : 'Preview'"
          :icon="preview ? 'pi pi-pencil' : 'pi pi-eye'"
          severity="secondary"
          text
          size="small"
          @click="preview = !preview"
        />
        <Button label="Save" icon="pi pi-save" size="small" @click="save" />
      </div>
    </div>

    <div v-if="preview" class="preview-pane" v-html="renderedHtml()"></div>
    <Textarea
      v-else
      v-model="editContent"
      class="editor-textarea"
      :rows="30"
    />
  </div>
</template>

<style scoped>
.editor-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.editor-path {
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.editor-actions {
  display: flex;
  gap: 0.5rem;
}

.editor-textarea {
  flex: 1;
  width: 100%;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 0.9rem;
  border: none;
  border-radius: 0;
  resize: none;
}

.preview-pane {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
  line-height: 1.6;
}

.preview-pane :deep(pre) {
  background: var(--p-surface-100);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
}
</style>
