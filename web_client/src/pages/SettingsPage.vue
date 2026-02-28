<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import { useToast } from 'primevue/usetoast'
import { Codemirror } from 'vue-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'
import { useConfigStore } from '../stores/config'
import { useChannelsStore } from '../stores/channels'
import { useApi } from '../composables/useApi'
import { useDark } from '../composables/useDark'
import DynamicForm from '../components/common/DynamicForm.vue'
import jsYaml from 'js-yaml'

const toast = useToast()
const configStore = useConfigStore()
const channelsStore = useChannelsStore()
const api = useApi()
const isDark = useDark()

const editorExtensions = computed(() => {
  const ext = [yaml()]
  if (isDark.value) ext.push(oneDark)
  return ext
})

const systemInfo = ref(null)
const systemInfoLoading = ref(true)
const formSchemas = ref({})

const bot = ref({ name: '', description: '' })
const serverConfig = ref({ host: '0.0.0.0', port: 8000, public_url: '', credential: '' })
const webClientConfig = ref({ credential: '' })
const credentials = ref({})
const providers = ref({})
const tools = ref({ general: { restrict_to_workspace: true }, exec: { timeout: 60 }, web_search: { credential: '', max_results: 5 } })
const storage = ref({ type: 'local', local_path: './workspace', s3_bucket: '', s3_region: '', credential: '' })
const imageConfig = ref({ model: '' })
const agentsConfig = ref({})
const telegram = ref({ enabled: false, credential: '', allowed_users: '', proxy: '', reply_to_message: false })
const activeTab = ref('info')
const rawYaml = ref('')
const yamlLoading = ref(false)
const restarting = ref(false)

const showSaveConfirm = ref(false)
const showRestartConfirm = ref(false)
const showAddAgent = ref(false)
const showAddCredential = ref(false)
const showAddProvider = ref(false)
const newAgentName = ref('')
const newCredentialName = ref('')
const newProviderName = ref('')

function humanize(name) {
  return name.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const references = computed(() => ({
  credentials: Object.keys(credentials.value),
  providers: Object.keys(providers.value),
}))

async function loadSystemInfo() {
  systemInfoLoading.value = true
  try {
    systemInfo.value = await api.get('/system/info')
  } catch {
    systemInfo.value = null
  } finally {
    systemInfoLoading.value = false
  }
}

async function loadFormSchemas() {
  try {
    formSchemas.value = await api.get('/forms')
  } catch {
    formSchemas.value = {}
  }
}

onMounted(async () => {
  await Promise.all([
    configStore.loadConfig(),
    channelsStore.loadChannels(),
    loadYaml(),
    loadSystemInfo(),
    loadFormSchemas(),
  ])
  if (configStore.config) {
    bot.value = { ...configStore.config.bot }
    const srv = configStore.config.server || {}
    serverConfig.value = {
      host: srv.host || '0.0.0.0',
      port: srv.port || 8000,
      public_url: srv.public_url || '',
      credential: srv.credential || '',
    }
    webClientConfig.value = { credential: configStore.config.web_client?.credential || '' }

    // credentials
    const cfgCreds = configStore.config.credentials || {}
    const parsedCreds = {}
    for (const [name, cred] of Object.entries(cfgCreds)) {
      parsedCreds[name] = { ...cred }
    }
    credentials.value = parsedCreds

    // providers
    const cfgProvs = configStore.config.providers || {}
    const parsedProvs = {}
    for (const [name, prov] of Object.entries(cfgProvs)) {
      parsedProvs[name] = { credential: prov.credential || '', base_url: prov.base_url || '' }
    }
    providers.value = parsedProvs

    tools.value = {
      general: {
        restrict_to_workspace: configStore.config.tools?.general?.restrict_to_workspace ?? true,
      },
      exec: { timeout: configStore.config.tools?.exec?.timeout ?? 60 },
      web_search: {
        credential: configStore.config.tools?.web_search?.credential || '',
        max_results: configStore.config.tools?.web_search?.max_results ?? 5,
      },
    }

    const st = configStore.config.storage || {}
    storage.value = {
      type: st.type || 'local',
      local_path: st.local_path || './workspace',
      s3_bucket: st.s3_bucket || '',
      s3_region: st.s3_region || '',
      credential: st.credential || '',
    }

    const img = configStore.config.image || {}
    imageConfig.value = { model: img.model || '' }

    const cfgAgents = configStore.config.agents || {}
    const parsedAgents = {}
    for (const [name, agent] of Object.entries(cfgAgents)) {
      parsedAgents[name] = {
        workspace: agent.workspace || '',
        description: agent.description || '',
        model: agent.model || '',
        instructions: agent.instructions || '',
        toolsStr: (agent.tools || []).join(', '),
      }
    }
    agentsConfig.value = parsedAgents

    const tg = configStore.config.channels?.telegram || {}
    telegram.value = {
      enabled: tg.enabled || false,
      credential: tg.credential || '',
      allowed_users: (tg.allowed_users || []).join(', '),
      proxy: tg.proxy || '',
      reply_to_message: tg.reply_to_message || false,
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

async function loadYaml() {
  yamlLoading.value = true
  try {
    const res = await api.get('/config/yaml')
    rawYaml.value = res.yaml || ''
  } catch {
    rawYaml.value = ''
  } finally {
    yamlLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'advanced') loadYaml()
})

function validateYaml() {
  try {
    jsYaml.load(rawYaml.value)
    toast.add({ severity: 'success', summary: 'Valid', detail: 'YAML syntax is correct', life: 2000 })
  } catch (e) {
    const line = e.mark ? e.mark.line + 1 : null
    const detail = line ? `Line ${line}: ${e.reason || e.message}` : e.message
    toast.add({ severity: 'error', summary: 'Invalid YAML', detail, life: 5000 })
  }
}

async function saveAdvanced() {
  showSaveConfirm.value = false
  try {
    const res = await api.put('/config/advanced', { data: { yaml: rawYaml.value } })
    if (res.error) {
      const detail = res.line ? `Line ${res.line}: ${res.error}` : res.error
      toast.add({ severity: 'error', summary: 'Error', detail, life: 5000 })
      return
    }
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Config updated', life: 2000 })
    await loadYaml()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}

async function restartServices() {
  showRestartConfirm.value = false
  restarting.value = true
  try {
    await api.post('/config/restart')
    toast.add({ severity: 'success', summary: 'Restarted', detail: 'All services restarted', life: 2000 })
    await channelsStore.loadChannels()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  } finally {
    restarting.value = false
  }
}

// agents
function confirmAddAgent() {
  const name = newAgentName.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (!name) return
  if (agentsConfig.value[name]) {
    toast.add({ severity: 'warn', summary: 'Exists', detail: `Agent "${name}" already exists`, life: 2000 })
    return
  }
  agentsConfig.value[name] = { workspace: '', description: '', model: '', instructions: '', toolsStr: '' }
  showAddAgent.value = false
}

function removeAgent(name) {
  const updated = { ...agentsConfig.value }
  delete updated[name]
  agentsConfig.value = updated
}

async function saveAgents() {
  const data = {}
  for (const [name, agent] of Object.entries(agentsConfig.value)) {
    data[name] = {
      workspace: agent.workspace,
      description: agent.description,
      model: agent.model,
      instructions: agent.instructions,
      tools: agent.toolsStr ? agent.toolsStr.split(',').map((s) => s.trim()).filter(Boolean) : [],
    }
  }
  await saveSection('agents', data)
}

// credentials
function confirmAddCredential() {
  const name = newCredentialName.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (!name) return
  if (credentials.value[name]) {
    toast.add({ severity: 'warn', summary: 'Exists', detail: `Credential "${name}" already exists`, life: 2000 })
    return
  }
  credentials.value[name] = { type: 'simple' }
  showAddCredential.value = false
}

function removeCredential(name) {
  const updated = { ...credentials.value }
  delete updated[name]
  credentials.value = updated
}

async function saveCredentials() {
  await saveSection('credentials', credentials.value)
}

// providers
function confirmAddProvider() {
  const name = newProviderName.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (!name) return
  if (providers.value[name]) {
    toast.add({ severity: 'warn', summary: 'Exists', detail: `Provider "${name}" already exists`, life: 2000 })
    return
  }
  providers.value[name] = { credential: '', base_url: '' }
  showAddProvider.value = false
}

function removeProvider(name) {
  const updated = { ...providers.value }
  delete updated[name]
  providers.value = updated
}

async function saveProviders() {
  await saveSection('providers', providers.value)
}

// channels
async function saveTelegram() {
  const config = {
    credential: telegram.value.credential,
    allowed_users: telegram.value.allowed_users.split(',').map((s) => s.trim()).filter(Boolean),
    proxy: telegram.value.proxy || null,
    reply_to_message: telegram.value.reply_to_message,
  }
  await channelsStore.updateChannel('telegram', config)
  toast.add({ severity: 'success', summary: 'Saved', detail: 'Telegram config updated', life: 2000 })
}

async function toggleTelegram(running) {
  try {
    if (running) {
      await channelsStore.stopChannel('telegram')
      toast.add({ severity: 'success', summary: 'Stopped', detail: 'Telegram channel stopped', life: 2000 })
    } else {
      await saveTelegram()
      await channelsStore.startChannel('telegram')
      toast.add({ severity: 'success', summary: 'Started', detail: 'Telegram channel started', life: 2000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to toggle Telegram channel', life: 3000 })
    await channelsStore.loadChannels()
  }
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>Settings</h2>
    </div>
    <div class="settings-content">
      <Tabs v-model:value="activeTab" :pt="{ root: { style: { flex: '1', display: 'flex', flexDirection: 'column' } } }">
        <TabList>
          <Tab value="info">Info</Tab>
          <Tab value="bot">Bot</Tab>
          <Tab value="server">Server</Tab>
          <Tab value="web_client">Web Client</Tab>
          <Tab value="agents">Agents</Tab>
          <Tab value="credentials">Credentials</Tab>
          <Tab value="providers">Providers</Tab>
          <Tab value="channels">Channels</Tab>
          <Tab value="storage">Storage</Tab>
          <Tab value="tools">Tools</Tab>
          <Tab value="image">Image</Tab>
          <Tab value="advanced">Advanced</Tab>
        </TabList>
        <TabPanels :pt="{ root: { style: { flex: '1' } } }">
          <!-- Info -->
          <TabPanel value="info" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div v-if="systemInfoLoading" class="info-loading">
                <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
              </div>
              <div v-else-if="!systemInfo" class="info-loading">
                <Message severity="error" :closable="false">Failed to load system information.</Message>
              </div>
              <template v-else>
                <div class="info-section">
                  <h3><i class="pi pi-desktop"></i> Operating System</h3>
                  <div class="info-row">
                    <span class="info-label">System</span>
                    <span class="info-value">{{ systemInfo.os.system }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Version</span>
                    <span class="info-value">{{ systemInfo.os.release }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Architecture</span>
                    <span class="info-value">{{ systemInfo.os.machine }}</span>
                  </div>
                </div>

                <div class="info-section">
                  <h3><i class="pi pi-microchip-ai"></i> Processor</h3>
                  <div class="info-row">
                    <span class="info-label">Model</span>
                    <span class="info-value">{{ systemInfo.cpu.processor }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Cores</span>
                    <span class="info-value">{{ systemInfo.cpu.cores }}</span>
                  </div>
                </div>

                <div v-if="systemInfo.memory.total_gb" class="info-section">
                  <h3><i class="pi pi-server"></i> Memory</h3>
                  <div class="info-row">
                    <span class="info-label">Total</span>
                    <span class="info-value">{{ systemInfo.memory.total_gb }} GB</span>
                  </div>
                </div>

                <div v-if="systemInfo.disk.total_gb" class="info-section">
                  <h3><i class="pi pi-database"></i> Disk</h3>
                  <div class="info-row">
                    <span class="info-label">Total</span>
                    <span class="info-value">{{ systemInfo.disk.total_gb }} GB</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Used</span>
                    <span class="info-value">{{ systemInfo.disk.used_gb }} GB ({{ systemInfo.disk.percent }}%)</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Free</span>
                    <span class="info-value">{{ systemInfo.disk.free_gb }} GB</span>
                  </div>
                  <ProgressBar :value="systemInfo.disk.percent" :show-value="false" style="height: 0.5rem; margin-top: 0.5rem" />
                </div>

                <div v-if="systemInfo.gpu?.length" class="info-section">
                  <h3><i class="pi pi-image"></i> Graphics</h3>
                  <template v-for="(gpu, i) in systemInfo.gpu" :key="i">
                    <div class="info-row">
                      <span class="info-label">{{ systemInfo.gpu.length > 1 ? `GPU ${i + 1}` : 'GPU' }}</span>
                      <span class="info-value">{{ gpu.name }}</span>
                    </div>
                    <div v-if="gpu.cores" class="info-row">
                      <span class="info-label">Cores</span>
                      <span class="info-value">{{ gpu.cores }}</span>
                    </div>
                    <div v-if="gpu.vendor" class="info-row">
                      <span class="info-label">Vendor</span>
                      <span class="info-value">{{ gpu.vendor }}</span>
                    </div>
                    <div v-if="gpu.metal" class="info-row">
                      <span class="info-label">Metal</span>
                      <span class="info-value">{{ gpu.metal }}</span>
                    </div>
                  </template>
                </div>

                <div class="info-section">
                  <h3><i class="pi pi-code"></i> Runtime</h3>
                  <div class="info-row">
                    <span class="info-label">Python</span>
                    <span class="info-value">{{ systemInfo.python }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">OpenBotX</span>
                    <span class="info-value">{{ systemInfo.version }}</span>
                  </div>
                </div>
              </template>
            </div>
          </TabPanel>

          <!-- Bot -->
          <TabPanel value="bot" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <DynamicForm v-if="formSchemas.bot" :schema="formSchemas.bot" v-model="bot" />
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('bot', bot)" />
            </div>
          </TabPanel>

          <!-- Server -->
          <TabPanel value="server" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <DynamicForm v-if="formSchemas.server" :schema="formSchemas.server" v-model="serverConfig" :references="references" />
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('server', serverConfig)" />
            </div>
          </TabPanel>

          <!-- Web Client -->
          <TabPanel value="web_client" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <DynamicForm v-if="formSchemas.web_client" :schema="formSchemas.web_client" v-model="webClientConfig" :references="references" />
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('web_client', webClientConfig)" />
            </div>
          </TabPanel>

          <!-- Agents -->
          <TabPanel value="agents" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div v-for="(agent, name) in agentsConfig" :key="name" class="item-block">
                <div class="item-header">
                  <i class="pi pi-user"></i>
                  <strong>{{ humanize(name) }}</strong>
                  <Button v-if="Object.keys(agentsConfig).length > 1" icon="pi pi-trash" severity="danger" text rounded size="small" @click="removeAgent(name)" />
                </div>
                <DynamicForm v-if="formSchemas.agent" :schema="formSchemas.agent" :model-value="agent" @update:model-value="agentsConfig[name] = $event" :references="references" />
                <div class="form-group">
                  <label>Tools (comma-separated, empty for all)</label>
                  <InputText v-model="agent.toolsStr" class="w-full" placeholder="tool_a, tool_b, tool_c, ..." />
                </div>
              </div>
              <div class="button-row">
                <Button label="Add Agent" icon="pi pi-plus" severity="secondary" size="small" @click="showAddAgent = true; newAgentName = ''" />
                <Button label="Save" icon="pi pi-save" size="small" @click="saveAgents" />
              </div>
            </div>
          </TabPanel>

          <!-- Credentials -->
          <TabPanel value="credentials" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div v-for="(cred, name) in credentials" :key="name" class="item-block">
                <div class="item-header">
                  <i class="pi pi-lock"></i>
                  <strong>{{ humanize(name) }}</strong>
                  <Button icon="pi pi-trash" severity="danger" text rounded size="small" @click="removeCredential(name)" />
                </div>
                <DynamicForm v-if="formSchemas.credential" :schema="formSchemas.credential" :model-value="cred" @update:model-value="credentials[name] = $event" :references="references" />
              </div>
              <div class="button-row">
                <Button label="Add Credential" icon="pi pi-plus" severity="secondary" size="small" @click="showAddCredential = true; newCredentialName = ''" />
                <Button label="Save" icon="pi pi-save" size="small" @click="saveCredentials" />
              </div>
            </div>
          </TabPanel>

          <!-- Providers -->
          <TabPanel value="providers" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div v-for="(prov, name) in providers" :key="name" class="item-block">
                <div class="item-header">
                  <i class="pi pi-box"></i>
                  <strong>{{ humanize(name) }}</strong>
                  <Button icon="pi pi-trash" severity="danger" text rounded size="small" @click="removeProvider(name)" />
                </div>
                <DynamicForm v-if="formSchemas.provider" :schema="formSchemas.provider" :model-value="prov" @update:model-value="providers[name] = $event" :references="references" />
              </div>
              <div class="button-row">
                <Button label="Add Provider" icon="pi pi-plus" severity="secondary" size="small" @click="showAddProvider = true; newProviderName = ''" />
                <Button label="Save" icon="pi pi-save" size="small" @click="saveProviders" />
              </div>
            </div>
          </TabPanel>

          <!-- Channels -->
          <TabPanel value="channels" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div class="item-block">
                <div class="item-header">
                  <i class="pi pi-globe"></i>
                  <strong>Web</strong>
                  <Tag value="running" severity="success" />
                </div>
                <p class="item-desc">Built-in web channel. Always active when the server is running.</p>
              </div>

              <div class="item-block">
                <div class="item-header">
                  <i class="pi pi-send"></i>
                  <strong>Telegram</strong>
                  <Tag
                    :value="channelsStore.channels?.telegram?.running ? 'running' : 'stopped'"
                    :severity="channelsStore.channels?.telegram?.running ? 'success' : 'danger'"
                  />
                </div>
                <DynamicForm v-if="formSchemas.channels_telegram" :schema="formSchemas.channels_telegram" v-model="telegram" :references="references" />
                <div class="button-row">
                  <Button label="Save" icon="pi pi-save" size="small" severity="secondary" @click="saveTelegram" />
                  <Button
                    :label="channelsStore.channels?.telegram?.running ? 'Stop' : 'Start'"
                    :icon="channelsStore.channels?.telegram?.running ? 'pi pi-stop' : 'pi pi-play'"
                    :severity="channelsStore.channels?.telegram?.running ? 'danger' : 'success'"
                    size="small"
                    @click="toggleTelegram(channelsStore.channels?.telegram?.running)"
                  />
                </div>
              </div>
            </div>
          </TabPanel>

          <!-- Storage -->
          <TabPanel value="storage" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <DynamicForm v-if="formSchemas.storage" :schema="formSchemas.storage" v-model="storage" :references="references" />
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('storage', storage)" />
            </div>
          </TabPanel>

          <!-- Tools -->
          <TabPanel value="tools" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div class="item-block">
                <div class="item-header">
                  <i class="pi pi-cog"></i>
                  <strong>General</strong>
                </div>
                <DynamicForm v-if="formSchemas.tools_general" :schema="formSchemas.tools_general" v-model="tools.general" />
              </div>

              <div class="item-block">
                <div class="item-header">
                  <i class="pi pi-code"></i>
                  <strong>Exec</strong>
                </div>
                <DynamicForm v-if="formSchemas.tools_exec" :schema="formSchemas.tools_exec" v-model="tools.exec" />
              </div>

              <div class="item-block">
                <div class="item-header">
                  <i class="pi pi-search"></i>
                  <strong>Web Search</strong>
                </div>
                <DynamicForm v-if="formSchemas.tools_web_search" :schema="formSchemas.tools_web_search" v-model="tools.web_search" :references="references" />
              </div>

              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('tools', tools)" />
            </div>
          </TabPanel>

          <!-- Image -->
          <TabPanel value="image" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <DynamicForm v-if="formSchemas.image" :schema="formSchemas.image" v-model="imageConfig" :references="references" />
              <Button label="Save" icon="pi pi-save" size="small" @click="saveSection('image', imageConfig)" />
            </div>
          </TabPanel>

          <!-- Advanced -->
          <TabPanel value="advanced" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content tab-content-wide">
              <Message severity="warn" :closable="false" class="tab-message">Edit raw config with care. Invalid changes may break the application.</Message>
              <div class="advanced-toolbar">
                <div class="toolbar-group">
                  <Button label="Reload" icon="pi pi-refresh" size="small" severity="secondary" :loading="yamlLoading" @click="loadYaml" />
                  <Button label="Validate" icon="pi pi-check-circle" size="small" severity="info" @click="validateYaml" :disabled="!rawYaml || yamlLoading" />
                </div>
                <div class="toolbar-group">
                  <Button label="Save" icon="pi pi-save" size="small" @click="showSaveConfirm = true" :disabled="!rawYaml || yamlLoading" />
                  <Button label="Restart" icon="pi pi-replay" size="small" severity="warn" :loading="restarting" @click="showRestartConfirm = true" />
                </div>
              </div>
              <div v-if="yamlLoading" class="yaml-loading">
                <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
              </div>
              <Codemirror v-else v-model="rawYaml" :extensions="editorExtensions" :style="{ fontSize: '0.85rem' }" class="yaml-editor" />
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>

    <!-- Dialogs -->
    <Dialog v-model:visible="showSaveConfirm" header="Confirm Save" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <p>Are you sure? This will overwrite the current configuration.</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showSaveConfirm = false" />
        <Button label="Save" icon="pi pi-save" size="small" @click="saveAdvanced" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showRestartConfirm" header="Confirm Restart" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <p>Are you sure? All services will be restarted.</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showRestartConfirm = false" />
        <Button label="Restart" icon="pi pi-replay" severity="warn" size="small" @click="restartServices" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showAddAgent" header="Add Agent" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="form-group">
        <label>Agent Name</label>
        <InputText v-model="newAgentName" class="w-full" placeholder="e.g. researcher" @keyup.enter="confirmAddAgent" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showAddAgent = false" />
        <Button label="Add" icon="pi pi-plus" size="small" @click="confirmAddAgent" :disabled="!newAgentName.trim()" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showAddCredential" header="Add Credential" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="form-group">
        <label>Credential Name</label>
        <InputText v-model="newCredentialName" class="w-full" placeholder="e.g. openai, twitter" @keyup.enter="confirmAddCredential" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showAddCredential = false" />
        <Button label="Add" icon="pi pi-plus" size="small" @click="confirmAddCredential" :disabled="!newCredentialName.trim()" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showAddProvider" header="Add Provider" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="form-group">
        <label>Provider Name</label>
        <InputText v-model="newProviderName" class="w-full" placeholder="e.g. anthropic, openai" @keyup.enter="confirmAddProvider" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showAddProvider = false" />
        <Button label="Add" icon="pi pi-plus" size="small" @click="confirmAddProvider" :disabled="!newProviderName.trim()" />
      </template>
    </Dialog>
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
  padding: 0.75rem;
}

.tab-content-wide {
  max-width: 800px;
}

.tab-message {
  margin-bottom: 1.25rem;
}

.form-group {
  margin-bottom: 0.75rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.button-row {
  display: flex;
  gap: 0.5rem;
}

.item-block {
  padding: 0.75rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  margin-bottom: 0.75rem;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.item-desc {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.advanced-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.toolbar-group {
  display: flex;
  gap: 0.5rem;
}

.yaml-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4rem 1rem;
  color: var(--p-text-muted-color);
}

.yaml-editor {
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  overflow: hidden;
}

.info-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--p-text-muted-color);
}

.info-section {
  margin-bottom: 1.25rem;
}

.info-section h3 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  color: var(--p-text-color);
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 0.35rem 0;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.info-row:last-of-type {
  border-bottom: none;
}

.info-label {
  color: var(--p-text-muted-color);
}

.info-value {
  font-weight: 600;
}

@media (max-width: 768px) {
  .tab-content {
    padding: 0.75rem;
  }

  .advanced-toolbar {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  .toolbar-group {
    display: contents;
  }
}
</style>
