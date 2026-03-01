<script setup>
import { ref, computed, onMounted } from 'vue'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import { useApi } from '../composables/useApi'

const api = useApi()
const tools = ref([])
const search = ref('')
const selectedTool = ref(null)
const dialogVisible = ref(false)
const loading = ref(true)

const filteredTools = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return tools.value
  return tools.value.filter(t =>
    t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
  )
})

onMounted(async () => {
  try {
    tools.value = await api.get('/tools')
  } finally {
    loading.value = false
  }
})

function viewTool(tool) {
  selectedTool.value = tool
  dialogVisible.value = true
}

const toolParams = computed(() => {
  if (!selectedTool.value?.parameters?.properties) return []
  const props = selectedTool.value.parameters.properties
  const required = selectedTool.value.parameters.required || []
  return Object.entries(props).map(([name, schema]) => ({
    name,
    type: schema.type || 'any',
    description: schema.description || '',
    required: required.includes(name),
    enum: schema.enum || null,
    minimum: schema.minimum,
    maximum: schema.maximum,
  }))
})
</script>

<template>
  <div class="tools-page">
    <div class="page-header">
      <h2>Tools</h2>
    </div>

    <div class="search-bar">
      <span class="p-input-icon-left search-input-wrapper">
        <i class="pi pi-search" />
        <InputText v-model="search" placeholder="Search tools..." class="search-input" />
      </span>
      <span v-if="!loading" class="search-count">{{ filteredTools.length }} tools</span>
    </div>

    <div v-if="loading" class="page-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
    </div>

    <div v-else-if="filteredTools.length" class="tools-grid">
      <Card v-for="tool in filteredTools" :key="tool.name" class="tool-card" @click="viewTool(tool)">
        <template #title>
          <div class="tool-name">
            <i class="pi pi-wrench"></i>
            {{ tool.name }}
          </div>
        </template>
        <template #subtitle>
          {{ tool.description }}
        </template>
      </Card>
    </div>

    <div v-else class="empty-state">
      <i class="pi pi-wrench" style="font-size: 2.5rem"></i>
      <p v-if="search">No tools matching "{{ search }}"</p>
      <p v-else>No tools registered</p>
    </div>

    <Dialog
      v-model:visible="dialogVisible"
      :header="selectedTool?.name"
      modal
      maximizable
      :style="{ width: '80vw', maxWidth: '700px' }"
      :breakpoints="{ '768px': '95vw' }"
    >
      <div v-if="selectedTool" class="tool-detail">
        <p class="tool-description">{{ selectedTool.description }}</p>

        <div v-if="toolParams.length" class="params-section">
          <h3>Parameters</h3>
          <div v-for="param in toolParams" :key="param.name" class="param-row">
            <div class="param-header">
              <code class="param-name">{{ param.name }}</code>
              <Tag :value="param.type" severity="secondary" />
              <Tag v-if="param.required" value="required" severity="warn" />
            </div>
            <p v-if="param.description" class="param-desc">{{ param.description }}</p>
            <div v-if="param.enum" class="param-meta">
              Values: <code v-for="(v, i) in param.enum" :key="v">{{ v }}<span v-if="i < param.enum.length - 1">, </span></code>
            </div>
            <div v-if="param.minimum != null || param.maximum != null" class="param-meta">
              Range: {{ param.minimum != null ? param.minimum : '...' }} – {{ param.maximum != null ? param.maximum : '...' }}
            </div>
          </div>
        </div>

        <div v-else class="params-section">
          <h3>Parameters</h3>
          <p class="param-desc">No parameters</p>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.tools-page {
  padding: 0;
}

.page-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.page-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.search-input-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  position: relative;
}

.search-input-wrapper i {
  position: absolute;
  left: 0.625rem;
  color: var(--p-text-muted-color);
  font-size: 0.85rem;
  z-index: 1;
}

.search-input {
  width: 100%;
  padding-left: 2rem;
}

.search-count {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.tool-card {
  cursor: pointer;
}

.tool-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tool-detail {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.tool-description {
  margin: 0;
  color: var(--p-text-muted-color);
  line-height: 1.5;
}

.params-section h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.param-row {
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
}

.param-row:last-child {
  border-bottom: none;
}

.param-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.param-name {
  font-family: ui-monospace, monospace;
  font-size: 0.9rem;
  font-weight: 600;
}

.param-desc {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.param-meta {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  margin-top: 0.2rem;
}

.param-meta code {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
}

.page-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--p-text-muted-color);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 1rem;
  color: var(--p-text-muted-color);
  gap: 0.75rem;
}
</style>
