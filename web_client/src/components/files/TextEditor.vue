<script setup>
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'

const props = defineProps({
  content: { type: String, default: '' },
  path: { type: String, default: '' },
})

const emit = defineEmits(['save'])
const editContent = ref(props.content)

watch(() => props.content, (val) => {
  editContent.value = val
})

function save() {
  emit('save', editContent.value)
}
</script>

<template>
  <div class="editor-container">
    <div class="editor-toolbar">
      <span class="editor-path">{{ path }}</span>
      <div class="editor-actions">
        <Button label="Save" icon="pi pi-save" size="small" @click="save" />
      </div>
    </div>
    <Textarea
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
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  border: none;
  border-radius: 0;
  resize: none;
  tab-size: 2;
}
</style>
