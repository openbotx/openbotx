<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Splitter from 'primevue/splitter'
import SplitterPanel from 'primevue/splitterpanel'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
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
const selectedItem = ref(null)
const isMobile = ref(window.innerWidth <= 768)

const showNewFileDialog = ref(false)
const showNewFolderDialog = ref(false)
const showDeleteDialog = ref(false)
const newFileName = ref('')
const newFolderName = ref('')
const createParentPath = ref('')
const deleteTarget = ref(null)
const uploadInput = ref(null)
const uploading = ref(false)
const loading = ref(true)

const isMarkdown = computed(() => {
  const p = currentFile.value?.path || ''
  return p.endsWith('.md')
})

const isHtmlFile = computed(() => {
  const name = selectedItem.value?.name || ''
  return /\.(html|htm)$/i.test(name)
})

const showBackButton = computed(() => isMobile.value && currentFile.value !== null)

function onResize() {
  isMobile.value = window.innerWidth <= 768
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    await loadFiles()
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})

async function loadFiles() {
  files.value = await api.get('/files')
}

async function refreshFiles() {
  clearSelection()
  await loadFiles()
}

function onSelect(item) {
  selectedItem.value = item
  if (item.type === 'file') {
    openFile(item.path)
  }
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
  selectedItem.value = null
}

function clearSelection() {
  selectedItem.value = null
  currentFile.value = null
}

function openCreateFile(parentPath) {
  createParentPath.value = parentPath
  newFileName.value = ''
  showNewFileDialog.value = true
}

function openCreateFolder(parentPath) {
  createParentPath.value = parentPath
  newFolderName.value = ''
  showNewFolderDialog.value = true
}

function openDeleteConfirm() {
  if (!selectedItem.value) return
  deleteTarget.value = selectedItem.value
  showDeleteDialog.value = true
}

async function confirmCreateFile() {
  const name = newFileName.value.trim()
  if (!name) return
  const path = createParentPath.value ? `${createParentPath.value}/${name}` : name
  try {
    const res = await api.post(`/files/create/${path}`)
    if (res.error) {
      toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 3000 })
      return
    }
    toast.add({ severity: 'success', summary: 'Created', detail: path, life: 2000 })
    showNewFileDialog.value = false
    await loadFiles()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}

async function confirmCreateFolder() {
  const name = newFolderName.value.trim()
  if (!name) return
  const path = createParentPath.value ? `${createParentPath.value}/${name}` : name
  try {
    const res = await api.post(`/files/mkdir/${path}`)
    if (res.error) {
      toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 3000 })
      return
    }
    toast.add({ severity: 'success', summary: 'Created', detail: path, life: 2000 })
    showNewFolderDialog.value = false
    await loadFiles()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}

function triggerUpload() {
  uploadInput.value?.click()
}

async function handleUpload(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return

  const targetDir = selectedItem.value?.type === 'directory' ? selectedItem.value.path : ''
  const uploadPath = targetDir ? `/files/upload/${targetDir}` : '/files/upload/'

  uploading.value = true
  try {
    const res = await api.upload(uploadPath, files)
    if (res.error) {
      toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 3000 })
      return
    }
    const count = res.paths?.length || files.length
    toast.add({ severity: 'success', summary: 'Uploaded', detail: `${count} file(s)`, life: 2000 })
    await loadFiles()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Upload failed', detail: e.message, life: 3000 })
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  const path = deleteTarget.value.path
  try {
    const res = await api.del(`/files/${path}`)
    if (res.error) {
      toast.add({ severity: 'error', summary: 'Error', detail: res.error, life: 3000 })
      return
    }
    toast.add({ severity: 'success', summary: 'Deleted', detail: path, life: 2000 })
    if (selectedItem.value?.path === path || selectedItem.value?.path?.startsWith(path + '/')) {
      selectedItem.value = null
    }
    if (currentFile.value?.path === path || currentFile.value?.path?.startsWith(path + '/')) {
      currentFile.value = null
    }
    showDeleteDialog.value = false
    await loadFiles()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}
</script>

<template>
  <div class="files-page">
    <input ref="uploadInput" type="file" multiple hidden @change="handleUpload" />

    <div class="files-header">
      <div class="header-left">
        <button v-if="showBackButton" class="back-btn" @click="closeFile">
          <i class="pi pi-arrow-left"></i>
          <span>Back</span>
        </button>
        <h2 v-else class="header-title" @click="clearSelection" title="Click to deselect">Files</h2>
      </div>

      <div v-if="selectedItem" class="header-center">
        <i :class="selectedItem.type === 'directory' ? 'pi pi-folder' : 'pi pi-file'" class="selected-icon"></i>
        <span class="selected-name">{{ selectedItem.name }}</span>
        <button class="deselect-btn" @click="clearSelection" title="Deselect">
          <i class="pi pi-times"></i>
        </button>
      </div>
      <div v-else class="header-center"></div>

      <div class="header-right">
        <Button v-if="!currentFile" icon="pi pi-refresh" size="small" text severity="secondary" title="Refresh" @click="refreshFiles" />
        <template v-if="!selectedItem">
          <Button icon="pi pi-upload" size="small" text severity="secondary" title="Upload to root" :loading="uploading" @click="triggerUpload" />
          <Button icon="pi pi-file-plus" size="small" text severity="secondary" title="New File" @click="openCreateFile('')" />
          <Button icon="pi pi-folder-plus" size="small" text severity="secondary" title="New Folder" @click="openCreateFolder('')" />
        </template>
        <template v-else-if="selectedItem.type === 'directory'">
          <Button icon="pi pi-upload" size="small" text severity="secondary" title="Upload here" :loading="uploading" @click="triggerUpload" />
          <Button icon="pi pi-file-plus" size="small" text severity="secondary" title="New File" @click="openCreateFile(selectedItem.path)" />
          <Button icon="pi pi-folder-plus" size="small" text severity="secondary" title="New Folder" @click="openCreateFolder(selectedItem.path)" />
          <Button icon="pi pi-trash" size="small" text severity="danger" title="Delete" @click="openDeleteConfirm" />
        </template>
        <template v-else>
          <a v-if="isHtmlFile" :href="`/api/files/download/${selectedItem.path}`" target="_blank" rel="noopener noreferrer" class="download-link">
            <Button icon="pi pi-external-link" size="small" text severity="secondary" title="Open in browser" />
          </a>
          <a :href="`/api/files/download/${selectedItem.path}`" :download="selectedItem.name" class="download-link">
            <Button icon="pi pi-download" size="small" text severity="secondary" title="Download" />
          </a>
          <Button icon="pi pi-trash" size="small" text severity="danger" title="Delete" @click="openDeleteConfirm" />
        </template>
      </div>
    </div>

    <div v-if="loading" class="page-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
    </div>

    <div v-else class="files-desktop">
      <Splitter class="files-splitter">
        <SplitterPanel :size="30" :min-size="20">
          <div class="tree-panel">
            <FileTree
              :files="files"
              :selected-key="selectedItem?.path || null"
              @select="onSelect"
            />
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

    <div v-if="!loading" class="files-mobile">
      <div v-if="!currentFile" class="tree-panel-mobile">
        <FileTree
          :files="files"
          :selected-key="selectedItem?.path || null"
          @select="onSelect"
        />
      </div>
      <div v-else class="editor-panel-mobile">
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

    <Dialog v-model:visible="showNewFileDialog" header="New File" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="dialog-content">
        <label>File name</label>
        <InputText v-model="newFileName" class="w-full" placeholder="example.txt" autofocus @keyup.enter="confirmCreateFile" />
        <small v-if="createParentPath" class="dialog-hint">In: {{ createParentPath }}/</small>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showNewFileDialog = false" />
        <Button label="Create" icon="pi pi-check" size="small" @click="confirmCreateFile" :disabled="!newFileName.trim()" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showNewFolderDialog" header="New Folder" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="dialog-content">
        <label>Folder name</label>
        <InputText v-model="newFolderName" class="w-full" placeholder="my-folder" autofocus @keyup.enter="confirmCreateFolder" />
        <small v-if="createParentPath" class="dialog-hint">In: {{ createParentPath }}/</small>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showNewFolderDialog = false" />
        <Button label="Create" icon="pi pi-check" size="small" @click="confirmCreateFolder" :disabled="!newFolderName.trim()" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showDeleteDialog" header="Confirm Delete" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="dialog-content" v-if="deleteTarget">
        <p>
          Are you sure you want to delete
          <strong>{{ deleteTarget.name }}</strong>?
        </p>
        <p v-if="deleteTarget.type === 'directory'" class="delete-warning">
          This will recursively delete the folder and all its contents.
        </p>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showDeleteDialog = false" />
        <Button label="Delete" icon="pi pi-trash" severity="danger" size="small" @click="confirmDelete" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.files-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.files-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  height: 3.25rem;
  box-sizing: border-box;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
  flex-shrink: 0;
  gap: 0.75rem;
}

.header-left {
  flex-shrink: 0;
}

.header-left h2 {
  margin: 0;
  font-size: 1.1rem;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0;
  border: none;
  background: none;
  color: var(--p-primary-color);
  font-size: 0.9rem;
  cursor: pointer;
}

.header-title {
  cursor: pointer;
}

.header-center {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.deselect-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: none;
  color: var(--p-text-muted-color);
  cursor: pointer;
  border-radius: 50%;
  flex-shrink: 0;
  font-size: 0.7rem;
}

.deselect-btn:hover {
  background: var(--p-content-hover-background);
  color: var(--p-text-color);
}

.selected-icon {
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.selected-name {
  font-size: 0.85rem;
  font-family: monospace;
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.download-link {
  display: inline-flex;
  text-decoration: none;
}

.page-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--p-text-muted-color);
  flex: 1;
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

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.dialog-content label {
  font-size: 0.85rem;
  font-weight: 600;
}

.dialog-hint {
  color: var(--p-text-muted-color);
}

.delete-warning {
  color: var(--p-red-500);
  font-size: 0.85rem;
  margin: 0;
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
    padding: 0;
  }

  .editor-panel-mobile {
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .files-header {
    padding: 0 0.75rem;
  }
}
</style>
