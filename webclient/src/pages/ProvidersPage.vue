<script setup>
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useApi } from '../composables/useApi'

const api = useApi()
const toast = useToast()
const providers = ref([])
const editState = ref({})

onMounted(async () => {
  providers.value = await api.get('/providers')
  providers.value.forEach((p) => {
    editState.value[p.name] = {
      api_key: '',
      api_base: p.api_base || '',
      params: p.params ? Object.entries(p.params).map(([k, v]) => ({ key: k, value: v })) : [],
    }
  })
})

function addParam(name) {
  editState.value[name].params.push({ key: '', value: '' })
}

function removeParam(name, index) {
  editState.value[name].params.splice(index, 1)
}

async function saveProvider(name) {
  const state = editState.value[name]
  const params = {}
  state.params.forEach((p) => {
    if (p.key.trim()) params[p.key.trim()] = p.value
  })
  await api.put(`/providers/${name}`, {
    api_key: state.api_key,
    api_base: state.api_base,
    params,
  })
  toast.add({ severity: 'success', summary: 'Saved', detail: `${name.charAt(0).toUpperCase() + name.slice(1)} updated`, life: 2000 })
  providers.value = await api.get('/providers')
  const updated = providers.value.find(p => p.name === name)
  editState.value[name].api_key = ''
  editState.value[name].api_base = updated?.api_base || ''
  editState.value[name].params = updated?.params
    ? Object.entries(updated.params).map(([k, v]) => ({ key: k, value: v }))
    : []
}
</script>

<template>
  <div class="providers-page">
    <div class="page-header">
      <h2>LLM Providers</h2>
    </div>
    <div class="providers-grid">
      <Card v-for="p in providers" :key="p.name">
        <template #title>
          <div class="provider-title">
            <i class="pi pi-server"></i>
            {{ p.name }}
            <Tag v-if="p.has_key" value="configured" severity="success" />
          </div>
        </template>
        <template #content>
          <div class="form-group">
            <label>API Key</label>
            <InputText
              v-model="editState[p.name].api_key"
              type="password"
              :placeholder="p.has_key ? '***' : 'Enter API key'"
              class="w-full"
            />
          </div>
          <div class="form-group">
            <label>Base URL (optional)</label>
            <InputText
              v-model="editState[p.name].api_base"
              :placeholder="p.api_base || 'Default'"
              class="w-full"
            />
          </div>
          <div class="form-group">
            <label>Parameters</label>
            <div v-for="(param, idx) in editState[p.name].params" :key="idx" class="param-row">
              <InputText v-model="param.key" placeholder="Key" class="param-key" />
              <InputText v-model="param.value" placeholder="Value" class="param-value" />
              <Button icon="pi pi-times" severity="danger" text size="small" @click="removeParam(p.name, idx)" />
            </div>
            <Button label="Add parameter" icon="pi pi-plus" severity="secondary" text size="small" @click="addParam(p.name)" />
          </div>
          <Button label="Save" icon="pi pi-save" size="small" @click="saveProvider(p.name)" />
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.providers-page {
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

.providers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.provider-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.param-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.5rem;
}

.param-key {
  flex: 1;
}

.param-value {
  flex: 1;
}
</style>
