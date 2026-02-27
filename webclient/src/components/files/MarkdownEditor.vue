<script setup>
import { ref, watch } from 'vue'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import Button from 'primevue/button'
import { useDark } from '../../composables/useDark'

const props = defineProps({
  content: { type: String, default: '' },
  path: { type: String, default: '' },
})

const emit = defineEmits(['save'])
const editContent = ref(props.content)
const editing = ref(false)
const isDark = useDark()

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
        <Button
          :label="editing ? 'Preview' : 'Edit'"
          :icon="editing ? 'pi pi-eye' : 'pi pi-pencil'"
          severity="secondary"
          text
          size="small"
          @click="editing = !editing"
        />
        <Button label="Save" icon="pi pi-save" size="small" @click="save" />
      </div>
    </div>

    <MdEditor
      v-if="editing"
      v-model="editContent"
      :theme="isDark ? 'dark' : 'light'"
      codeTheme="github"
      :codeStyleReverse="false"
      language="en-US"
      :preview="false"
      :toolbars="['bold', 'underline', 'italic', 'strikeThrough', '-',
        'title', 'sub', 'sup', 'quote', 'unorderedList', 'orderedList', 'task', '-',
        'codeRow', 'code', 'link', 'image', 'table', '-',
        'revoke', 'next', '=',
        'preview', 'fullscreen']"
      class="md-editor-fill"
    />
    <MdPreview
      v-else
      :modelValue="editContent"
      :theme="isDark ? 'dark' : 'light'"
      codeTheme="github"
      :codeStyleReverse="false"
      language="en-US"
      class="md-preview-fill"
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

.md-editor-fill {
  flex: 1;
  min-height: 0;
}

.md-preview-fill {
  flex: 1;
  min-height: 0;
  padding: 0 1.5rem;
  overflow-y: auto;
}
</style>
