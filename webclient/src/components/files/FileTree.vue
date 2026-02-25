<script setup>
import { ref } from 'vue'
import Tree from 'primevue/tree'
import Button from 'primevue/button'

const props = defineProps({
  files: { type: Array, default: () => [] },
})

const emit = defineEmits(['select', 'create-file', 'create-folder', 'delete'])
const expandedKeys = ref({})

function toTreeNodes(items) {
  const sorted = [...items].sort((a, b) => {
    if (a.type === 'directory' && b.type !== 'directory') return -1
    if (a.type !== 'directory' && b.type === 'directory') return 1
    return a.name.localeCompare(b.name)
  })
  return sorted.map((item) => {
    const node = {
      key: item.path,
      label: item.name,
      icon: item.type === 'directory' ? 'pi pi-folder' : fileIcon(item.name),
      data: item,
      leaf: item.type !== 'directory',
    }
    if (item.type === 'directory') {
      node.children = toTreeNodes(item.children || [])
    }
    return node
  })
}

function fileIcon(name) {
  const ext = name.split('.').pop().toLowerCase()
  const icons = {
    md: 'pi pi-file-edit',
    json: 'pi pi-code',
    jsonl: 'pi pi-code',
    yml: 'pi pi-code',
    yaml: 'pi pi-code',
    py: 'pi pi-code',
    js: 'pi pi-code',
    ts: 'pi pi-code',
    html: 'pi pi-code',
    css: 'pi pi-code',
    txt: 'pi pi-file',
    log: 'pi pi-file',
    csv: 'pi pi-file',
    pdf: 'pi pi-file-pdf',
    png: 'pi pi-image',
    jpg: 'pi pi-image',
    jpeg: 'pi pi-image',
    gif: 'pi pi-image',
    svg: 'pi pi-image',
    webp: 'pi pi-image',
    zip: 'pi pi-box',
    tar: 'pi pi-box',
    gz: 'pi pi-box',
  }
  return icons[ext] || 'pi pi-file'
}

function onNodeSelect(node) {
  if (node.data && node.data.type === 'file') {
    emit('select', node.data.path)
  }
}
</script>

<template>
  <div class="file-tree-wrapper">
    <div class="file-tree-toolbar">
      <Button icon="pi pi-file-plus" size="small" text severity="secondary" title="New File" @click="emit('create-file', '')" />
      <Button icon="pi pi-folder-plus" size="small" text severity="secondary" title="New Folder" @click="emit('create-folder', '')" />
    </div>
    <Tree
      :value="toTreeNodes(files)"
      v-model:expandedKeys="expandedKeys"
      selection-mode="single"
      @node-select="onNodeSelect"
      class="file-tree"
    >
      <template #default="{ node }">
        <div class="tree-node">
          <span class="tree-node-label">{{ node.label }}</span>
          <span class="tree-node-actions">
            <button
              v-if="node.data?.type === 'directory'"
              class="node-action-btn"
              title="New file here"
              @click.stop="emit('create-file', node.data.path)"
            >
              <i class="pi pi-file-plus"></i>
            </button>
            <button
              v-if="node.data?.type === 'directory'"
              class="node-action-btn"
              title="New folder here"
              @click.stop="emit('create-folder', node.data.path)"
            >
              <i class="pi pi-folder-plus"></i>
            </button>
            <button
              class="node-action-btn node-action-delete"
              title="Delete"
              @click.stop="emit('delete', node.data)"
            >
              <i class="pi pi-trash"></i>
            </button>
          </span>
        </div>
      </template>
    </Tree>
  </div>
</template>

<style scoped>
.file-tree-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.file-tree-toolbar {
  display: flex;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.file-tree {
  border: none;
  background: transparent;
  padding: 0;
  flex: 1;
  overflow-y: auto;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.tree-node-label {
  overflow-wrap: break-word;
  word-break: break-all;
  min-width: 0;
  flex: 1;
}

.tree-node-actions {
  display: none;
  gap: 0.1rem;
  margin-left: auto;
  flex-shrink: 0;
}

.tree-node:hover .tree-node-actions {
  display: flex;
}

.node-action-btn {
  border: none;
  background: transparent;
  color: var(--p-text-muted-color);
  cursor: pointer;
  padding: 0.15rem;
  border-radius: 3px;
  font-size: 0.75rem;
  line-height: 1;
}

.node-action-btn:hover {
  background: var(--p-content-hover-background);
  color: var(--p-text-color);
}

.node-action-delete:hover {
  color: var(--p-red-500);
}

@media (hover: none) {
  .tree-node-actions {
    display: flex;
  }
}
</style>
