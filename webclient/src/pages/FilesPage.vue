<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import FileTree from '../components/files/FileTree.vue'
import MarkdownEditor from '../components/files/MarkdownEditor.vue'
import TextEditor from '../components/files/TextEditor.vue'
import MediaPreview from '../components/files/MediaPreview.vue'
import FileDownload from '../components/files/FileDownload.vue'
import { useApi } from '../composables/useApi'

const api = useApi()
const toast = useToast()
const files = ref([])
const currentFile = ref(null)

const isMarkdown = computed(() => {
  const p = currentFile.value?.path || ''
  return p.endsWith('.md')
})

onMounted(async () => {
  await loadFiles()
})

async function loadFiles() {
  files.value = await api.get('/files')
}

async function openFile(path) {
  const data = await api.get(`/files/${path}`)
  if (data.error) {
    toast.add({ severity: 'error', summary: 'Error', detail: data.error, life: 3000 })
    return
  }
  currentFile.value = data
}

async function saveFile(content) {
  const path = currentFile.value?.path
  if (!path) return
  await api.put(`/files/${path}`, { content })
  toast.add({ severity: 'success', summary: 'Saved', detail: path, life: 2000 })
  await loadFiles()
}

function closeFile() {
  currentFile.value = null
}
</script>

<template>
  <div class="files-page">
    <div class="files-header">
      <h2>Files</h2>
    </div>

    <div class="files-desktop">
      <Splitter class="files-splitter">
        <SplitterPanel :size="30" :min-size="20">
          <div class="tree-panel">
            <FileTree :files="files" @select="openFile" />
          </div>
        </SplitterPanel>
        <SplitterPanel :size="70" :min-size="40">
          <template v-if="currentFile">
            <MarkdownEditor
              v-if="currentFile.type === 'text' && isMarkdown"
              :content="currentFile.content"
              :path="currentFile.path"
              @save="saveFile"
            />
            <TextEditor
              v-else-if="currentFile.type === 'text'"
              :content="currentFile.content"
              :path="currentFile.path"
              @save="saveFile"
            />
            <MediaPreview
              v-else-if="['image', 'video', 'audio'].includes(currentFile.type)"
              :path="currentFile.path"
              :type="currentFile.type"
              :mime="currentFile.mime"
              :size="currentFile.size"
              :url="currentFile.url"
            />
            <FileDownload
              v-else
              :path="currentFile.path"
              :mime="currentFile.mime"
              :size="currentFile.size"
              :url="currentFile.url"
            />
          </template>
          <div v-else class="no-file">
            <i class="pi pi-file" style="font-size: 3rem; color: var(--p-text-muted-color)"></i>
            <p>Select a file to edit</p>
          </div>
        </SplitterPanel>
      </Splitter>
    </div>

    <div class="files-mobile">
      <div v-if="!currentFile" class="tree-panel-mobile">
        <FileTree :files="files" @select="openFile" />
      </div>
      <div v-else class="editor-panel-mobile">
        <button class="back-btn" @click="closeFile">
          <i class="pi pi-arrow-left"></i> Back to files
        </button>
        <MarkdownEditor
          v-if="currentFile.type === 'text' && isMarkdown"
          :content="currentFile.content"
          :path="currentFile.path"
          @save="saveFile"
        />
        <TextEditor
          v-else-if="currentFile.type === 'text'"
          :content="currentFile.content"
          :path="currentFile.path"
          @save="saveFile"
        />
        <MediaPreview
          v-else-if="['image', 'video', 'audio'].includes(currentFile.type)"
          :path="currentFile.path"
          :type="currentFile.type"
          :mime="currentFile.mime"
          :size="currentFile.size"
          :url="currentFile.url"
        />
        <FileDownload
          v-else
          :path="currentFile.path"
          :mime="currentFile.mime"
          :size="currentFile.size"
          :url="currentFile.url"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.files-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.files-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.files-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.files-desktop {
  flex: 1;
  display: flex;
  min-height: 0;
}

.files-splitter {
  flex: 1;
  border: none;
}

.tree-panel {
  padding: 0.5rem;
  overflow-y: auto;
  height: 100%;
}

.no-file {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--p-text-muted-color);
  gap: 1rem;
}

.files-mobile {
  display: none;
}

@media (max-width: 768px) {
  .files-desktop {
    display: none;
  }

  .files-mobile {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: auto;
  }

  .tree-panel-mobile {
    padding: 0.5rem;
  }

  .editor-panel-mobile {
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .back-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border: none;
    border-bottom: 1px solid var(--p-content-border-color);
    background: var(--p-content-background);
    color: var(--p-primary-color);
    font-size: 0.9rem;
    cursor: pointer;
  }

  .files-header {
    padding: 0.5rem 0.75rem;
  }
}
</style>
