<script setup>
import { ref, computed } from 'vue'
import Tree from 'primevue/tree'

const props = defineProps({
  files: { type: Array, default: () => [] },
  selectedKey: { type: String, default: null },
})

const emit = defineEmits(['select'])
const expandedKeys = ref({})

const selectionKeys = computed(() => {
  if (!props.selectedKey) return {}
  return { [props.selectedKey]: true }
})

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
  if (node.data) {
    emit('select', node.data)
  }
}
</script>

<template>
  <div class="file-tree-wrapper">
    <Tree
      :value="toTreeNodes(files)"
      v-model:expandedKeys="expandedKeys"
      :selectionKeys="selectionKeys"
      selection-mode="single"
      @node-select="onNodeSelect"
      class="file-tree"
    >
      <template #default="{ node }">
        <span class="tree-node-label">{{ node.label }}</span>
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

.file-tree {
  border: none;
  background: transparent;
  padding: 0;
  flex: 1;
  overflow-y: auto;
}

.tree-node-label {
  overflow-wrap: break-word;
  word-break: break-all;
  min-width: 0;
}
</style>
