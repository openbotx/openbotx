<script setup>
import { ref, onMounted, computed } from 'vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import Divider from 'primevue/divider'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import { useConfigStore } from '../stores/config'
import { useApi } from '../composables/useApi'

const toast = useToast()
const configStore = useConfigStore()
const api = useApi()

const bot = ref({ name: '', description: '' })
const agents = ref({})
const newAgentName = ref('')
const image = ref({ provider: 'gemini', model: 'gemini-3-pro-image-preview', api_key: '' })
const auth = ref({ username: 'admin', password: '' })
const tools = ref({ restrict_to_workspace: true, exec: { timeout: 60 }, web_search: { api_key: '', max_results: 5 } })
const storage = ref({ type: 'local', s3_bucket: '', s3_region: 'us-east-1', s3_access_key: '', s3_secret_key: '' })
const rawYaml = ref('')
const restarting = ref(false)

const defaultParams = { max_tokens: 8192, temperature: 0.1, max_iterations: 40, memory_window: 100 }

const storageTypes = ref([
  { label: 'Local', value: 'local' },
  { label: 'Amazon S3', value: 's3' },
])

const isS3 = computed(() => storage.value.type === 's3')
const agentEntries = computed(() => Object.entries(agents.value))

onMounted(async () => {
  await configStore.loadConfig()
  if (configStore.config) {
    bot.value = { ...configStore.config.bot }

    const cfgAgents = configStore.config.agents || {}
    const loaded = {}
    for (const [key, val] of Object.entries(cfgAgents)) {
      loaded[key] = {
        model: val.model || '',
        params: { ...defaultParams, ...(val.params || {}) },
      }
    }
    if (!loaded.main) {
      loaded.main = { model: 'anthropic/claude-sonnet-4-20250514', params: { ...defaultParams } }
    }
    agents.value = loaded

    const cfgImage = configStore.config.image || {}
    image.value = {
      provider: cfgImage.provider || 'gemini',
      model: cfgImage.model || 'gemini-3-pro-image-preview',
      api_key: '',
    }
    const cfgAuth = configStore.config.auth || {}
    auth.value = { username: cfgAuth.username || 'admin', password: '', secret_key: '' }
    tools.value = {
      restrict_to_workspace: configStore.config.tools?.restrict_to_workspace ?? true,
      exec: { timeout: configStore.config.tools?.exec?.timeout ?? 60 },
      web_search: { api_key: '', max_results: configStore.config.tools?.web_search?.max_results ?? 5 },
    }
    const st = configStore.config.storage || {}
    storage.value = {
      type: st.type || 'local',
      s3_bucket: st.s3_bucket || '',
      s3_region: st.s3_region || 'us-east-1',
      s3_access_key: '',
      s3_secret_key: '',
    }
  }
})

async function saveSection(section, data) {
  try {
    await configStore.saveSection(section, data)
    toast.add({ severity: 'success', summary: 'Saved', detail: `${section.charAt(0).toUpperCase() + section.slice(1)} updated`, life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}

function addAgent() {
  const name = newAgentName.value.trim()
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  if (!slug) {
    toast.add({ severity: 'warn', summary: 'Invalid', detail: 'Enter a valid agent name', life: 2000 })
    return
  }
  if (agents.value[slug]) {
    toast.add({ severity: 'warn', summary: 'Exists', detail: `Agent "${slug}" already exists`, life: 2000 })
    return
  }
  agents.value[slug] = { model: 'anthropic/claude-sonnet-4-20250514', params: { ...defaultParams } }
  newAgentName.value = ''
}

function removeAgent(key) {
  if (key === 'main') return
  delete agents.value[key]
}

async function saveAgents() {
  const data = {}
  for (const [key, val] of Object.entries(agents.value)) {
    data[key] = { model: val.model, params: { ...val.params } }
  }
  await saveSection('agents', data)
}

async function saveImage() {
  await saveSection('image', image.value)
}

async function loadRawYaml() {
  await configStore.loadConfig()
  rawYaml.value = JSON.stringify(configStore.config, null, 2)
}

async function saveAdvanced() {
  try {
    const parsed = JSON.parse(rawYaml.value)
    await api.put('/config/advanced', { data: parsed })
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Config updated', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}

async function restartServices() {
  restarting.value = true
  try {
    await api.post('/config/restart')
    toast.add({ severity: 'success', summary: 'Restarted', detail: 'All services restarted', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  } finally {
    restarting.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>Settings</h2>
    </div>
    <div class="settings-content">
      <Tabs value="bot" :pt="{ root: { style: { flex: '1', display: 'flex', flexDirection: 'column' } } }">
        <TabList>
          <Tab value="bot">Bot</Tab>
          <Tab value="agents">Agents</Tab>
          <Tab value="storage">Storage</Tab>
          <Tab value="tools">Tools</Tab>
          <Tab value="auth">Auth</Tab>
          <Tab value="advanced">Advanced</Tab>
        </TabList>
        <TabPanels :pt="{ root: { style: { flex: '1' } } }">
          <TabPanel value="bot" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div class="form-group">
                <label>Name</label>
                <InputText v-model="bot.name" class="w-full" />
              </div>
              <div class="form-group">
                <label>Description</label>
                <InputText v-model="bot.description" class="w-full" />
              </div>
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('bot', bot)" />
            </div>
          </TabPanel>

          <TabPanel value="agents" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div v-for="([key, agent]) in agentEntries" :key="key" class="agent-block">
                <div class="agent-header">
                  <h3>{{ key }}</h3>
                  <Button v-if="key !== 'main'" icon="pi pi-trash" severity="danger" text size="small" @click="removeAgent(key)" />
                </div>
                <div class="form-group">
                  <label>Model</label>
                  <InputText v-model="agent.model" class="w-full" placeholder="anthropic/claude-sonnet-4-20250514" />
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>Temperature</label>
                    <InputNumber v-model="agent.params.temperature" :min="0" :max="2" :step="0.1" :min-fraction-digits="1" class="w-full" />
                  </div>
                  <div class="form-group">
                    <label>Max Tokens</label>
                    <InputNumber v-model="agent.params.max_tokens" :step="1024" class="w-full" />
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>Max Iterations</label>
                    <InputNumber v-model="agent.params.max_iterations" class="w-full" />
                  </div>
                  <div class="form-group">
                    <label>Memory Window</label>
                    <InputNumber v-model="agent.params.memory_window" class="w-full" />
                  </div>
                </div>
                <Divider />
              </div>

              <div class="add-agent-row">
                <InputText v-model="newAgentName" placeholder="New agent name" class="add-agent-input" @keyup.enter="addAgent" />
                <Button label="Add Agent" icon="pi pi-plus" size="small" severity="secondary" @click="addAgent" />
              </div>

              <div class="save-row">
                <Button label="Save Agents" icon="pi pi-save" size="small" @click="saveAgents" />
              </div>

              <Divider />

              <h3>Image Generation</h3>
              <div class="form-group">
                <label>Provider</label>
                <InputText v-model="image.provider" class="w-full" placeholder="gemini" />
              </div>
              <div class="form-group">
                <label>Model</label>
                <InputText v-model="image.model" class="w-full" placeholder="gemini-3-pro-image-preview" />
              </div>
              <div class="form-group">
                <label>API Key</label>
                <Password v-model="image.api_key" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
              </div>
              <Button label="Save Image" icon="pi pi-save" size="small" @click="saveImage" />
            </div>
          </TabPanel>

          <TabPanel value="storage" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div class="form-group">
                <label>Type</label>
                <Select v-model="storage.type" :options="storageTypes" option-label="label" option-value="value" class="w-full" />
              </div>
              <template v-if="!isS3">
                <Message severity="info" :closable="false" class="tab-message">Files are stored in the workspace directory.</Message>
              </template>
              <template v-if="isS3">
                <div class="form-group">
                  <label>S3 Bucket</label>
                  <InputText v-model="storage.s3_bucket" class="w-full" />
                </div>
                <div class="form-group">
                  <label>S3 Region</label>
                  <InputText v-model="storage.s3_region" class="w-full" />
                </div>
                <div class="form-group">
                  <label>Access Key</label>
                  <Password v-model="storage.s3_access_key" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                </div>
                <div class="form-group">
                  <label>Secret Key</label>
                  <Password v-model="storage.s3_secret_key" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                </div>
              </template>
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('storage', storage)" />
            </div>
          </TabPanel>

          <TabPanel value="tools" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div class="form-group">
                <label>Restrict to Workspace</label>
                <ToggleSwitch v-model="tools.restrict_to_workspace" />
              </div>
              <div class="form-group">
                <label>Exec Timeout (seconds)</label>
                <InputNumber v-model="tools.exec.timeout" class="w-full" />
              </div>
              <Divider />
              <h3>Web Search</h3>
              <div class="form-group">
                <label>Brave API Key</label>
                <Password v-model="tools.web_search.api_key" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
              </div>
              <div class="form-group">
                <label>Max Results</label>
                <InputNumber v-model="tools.web_search.max_results" :min="1" :max="20" class="w-full" />
              </div>
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('tools', tools)" />
            </div>
          </TabPanel>

          <TabPanel value="auth" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <Message severity="info" :closable="false" class="tab-message">Changes take effect on next server restart.</Message>
              <div class="form-group">
                <label>Username</label>
                <InputText v-model="auth.username" class="w-full" autocomplete="off" />
              </div>
              <div class="form-group">
                <label>Password</label>
                <Password v-model="auth.password" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="new-password" placeholder="Leave empty to keep current" />
              </div>
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('auth', auth)" />
            </div>
          </TabPanel>

          <TabPanel value="advanced" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <Message severity="warn" :closable="false" class="tab-message">Edit raw config with care. Invalid changes may break the application.</Message>
              <div class="form-group">
                <Button label="Load Current Config" icon="pi pi-refresh" size="small" severity="secondary" @click="loadRawYaml" />
              </div>
              <div class="form-group">
                <Textarea v-model="rawYaml" rows="20" class="w-full raw-editor" auto-resize />
              </div>
              <div class="button-row">
                <Button label="Save Config" icon="pi pi-save" size="small" @click="saveAdvanced" :disabled="!rawYaml" />
                <Button label="Restart Services" icon="pi pi-replay" size="small" severity="warn" :loading="restarting" @click="restartServices" />
              </div>
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.page-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.settings-content {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.tab-content {
  max-width: 600px;
  padding: 1rem;
}

.tab-content h3 {
  margin: 0 0 1rem;
  font-size: 1rem;
}

.tab-message {
  margin-bottom: 1.25rem;
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

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row .form-group {
  flex: 1;
}

.agent-block {
  margin-bottom: 0.5rem;
}

.agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.agent-header h3 {
  margin: 0;
}

.add-agent-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 1rem;
}

.add-agent-input {
  flex: 1;
}

.save-row {
  margin-bottom: 1rem;
}

.button-row {
  display: flex;
  gap: 0.5rem;
}

.raw-editor {
  font-family: monospace;
  font-size: 0.85rem;
}

@media (max-width: 768px) {
  .form-row {
    flex-direction: column;
    gap: 0;
  }

  .tab-content {
    padding: 0.75rem;
  }
}
</style>
