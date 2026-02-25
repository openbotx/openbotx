<script setup>
import Tree from 'primevue/tree'

const props = defineProps({
  files: { type: Array, default: () => [] },
})

const emit = defineEmits(['select'])

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
  <Tree
    :value="toTreeNodes(files)"
    selection-mode="single"
    :pt="{ nodeLabel: { style: { overflowWrap: 'break-word', wordBreak: 'break-all', minWidth: '0' } } }"
    @node-select="onNodeSelect"
    class="file-tree"
  />
</template>

<style scoped>
.file-tree {
  border: none;
  background: transparent;
  padding: 0;
}
</style>
