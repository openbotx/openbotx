<script setup>
import { ref, computed, onMounted } from 'vue'
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
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'
import { useToast } from 'primevue/usetoast'
import { useConfigStore } from '../stores/config'
import { useChannelsStore } from '../stores/channels'
import { useApi } from '../composables/useApi'
import jsYaml from 'js-yaml'

const toast = useToast()
const configStore = useConfigStore()
const channelsStore = useChannelsStore()
const api = useApi()

const systemInfo = ref(null)
const systemInfoLoading = ref(true)

const bot = ref({ name: '', description: '' })
const auth = ref({ username: 'admin', password: '', secret_key: '' })
const tools = ref({ general: { restrict_to_workspace: true }, exec: { timeout: 60 }, web_search: { api_key: '', max_results: 5 }, http_client: { auth_profiles: {} } })
const storage = ref({ type: 'local', s3_bucket: '', s3_region: 'us-east-1', s3_access_key: '', s3_secret_key: '' })
const agentsConfig = ref({})
const rawYaml = ref('')
const restarting = ref(false)

const telegramToken = ref('')
const telegramUsers = ref('')

const showSaveConfirm = ref(false)
const showRestartConfirm = ref(false)

const storageTypes = ref([
  { label: 'Local', value: 'local' },
  { label: 'Amazon S3', value: 's3' },
])

const isS3 = computed(() => storage.value.type === 's3')

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

onMounted(async () => {
  await Promise.all([
    configStore.loadConfig(),
    channelsStore.loadChannels(),
    loadYaml(),
    loadSystemInfo(),
  ])
  if (configStore.config) {
    bot.value = { ...configStore.config.bot }

    const cfgAuth = configStore.config.auth || {}
    auth.value = { username: cfgAuth.username || 'admin', password: '', secret_key: '' }
    tools.value = {
      general: {
        restrict_to_workspace: configStore.config.tools?.general?.restrict_to_workspace ?? true,
      },
      exec: { timeout: configStore.config.tools?.exec?.timeout ?? 60 },
      web_search: { api_key: '', max_results: configStore.config.tools?.web_search?.max_results ?? 5 },
      http_client: { auth_profiles: parseAuthProfiles(configStore.config.tools?.http_client?.auth_profiles) },
    }
    const st = configStore.config.storage || {}
    storage.value = {
      type: st.type || 'local',
      s3_bucket: st.s3_bucket || '',
      s3_region: st.s3_region || 'us-east-1',
      s3_access_key: '',
      s3_secret_key: '',
    }

    const cfgAgents = configStore.config.agents || {}
    const parsed = {}
    for (const [name, agent] of Object.entries(cfgAgents)) {
      parsed[name] = {
        description: agent.description || '',
        model: agent.model || '',
        instructions: agent.instructions || '',
        toolsStr: (agent.tools || []).join(', '),
      }
    }
    agentsConfig.value = parsed
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
  try {
    const res = await api.get('/config/yaml')
    rawYaml.value = res.yaml || ''
  } catch {
    rawYaml.value = ''
  }
}

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

async function saveTelegram() {
  const config = {}
  if (telegramToken.value) config.token = telegramToken.value
  config.allowed_users = telegramUsers.value.split(',').map((s) => s.trim()).filter(Boolean)
  await channelsStore.updateChannel('telegram', config)
  toast.add({ severity: 'success', summary: 'Saved', detail: 'Telegram config updated', life: 2000 })
}

async function toggleTelegram(running) {
  try {
    if (running) {
      await channelsStore.stopChannel('telegram')
      toast.add({ severity: 'success', summary: 'Stopped', detail: 'Telegram channel stopped', life: 2000 })
    } else {
      if (telegramToken.value || telegramUsers.value) {
        await saveTelegram()
      }
      await channelsStore.startChannel('telegram')
      toast.add({ severity: 'success', summary: 'Started', detail: 'Telegram channel started', life: 2000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to toggle Telegram channel', life: 3000 })
    await channelsStore.loadChannels()
  }
}

const authTypes = ref([
  { label: 'OAuth 1.0a', value: 'oauth1' },
  { label: 'Basic', value: 'basic' },
  { label: 'Bearer', value: 'bearer' },
])

const newProfileName = ref('')
const showAddProfile = ref(false)

function parseAuthProfiles(profiles) {
  if (!profiles || typeof profiles !== 'object') return {}
  const result = {}
  for (const [name, p] of Object.entries(profiles)) {
    result[name] = {
      type: p.type || 'bearer',
      consumer_key: '', consumer_secret: '', access_token: '', access_token_secret: '',
      username: '', password: '',
      token: '',
    }
  }
  return result
}

function emptyProfile(type = 'bearer') {
  return {
    type,
    consumer_key: '', consumer_secret: '', access_token: '', access_token_secret: '',
    username: '', password: '',
    token: '',
  }
}

function addAuthProfile() {
  showAddProfile.value = true
  newProfileName.value = ''
}

function confirmAddProfile() {
  const name = newProfileName.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (!name) return
  if (tools.value.http_client.auth_profiles[name]) {
    toast.add({ severity: 'warn', summary: 'Exists', detail: `Profile "${name}" already exists`, life: 2000 })
    return
  }
  tools.value.http_client.auth_profiles[name] = emptyProfile()
  showAddProfile.value = false
}

function removeAuthProfile(name) {
  const updated = { ...tools.value.http_client.auth_profiles }
  delete updated[name]
  tools.value.http_client.auth_profiles = updated
}

const newAgentName = ref('')
const showAddAgent = ref(false)

function addAgent() {
  showAddAgent.value = true
  newAgentName.value = ''
}

function confirmAddAgent() {
  const name = newAgentName.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (!name) return
  if (agentsConfig.value[name]) {
    toast.add({ severity: 'warn', summary: 'Exists', detail: `Agent "${name}" already exists`, life: 2000 })
    return
  }
  agentsConfig.value[name] = {
    description: '',
    model: '',
    instructions: '',
    toolsStr: '',
  }
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
      description: agent.description,
      model: agent.model,
      instructions: agent.instructions,
      tools: agent.toolsStr ? agent.toolsStr.split(',').map((s) => s.trim()).filter(Boolean) : [],
    }
  }
  try {
    await configStore.saveSection('agents', data)
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Agents updated', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>Settings</h2>
    </div>
    <div class="settings-content">
      <Tabs value="info" :pt="{ root: { style: { flex: '1', display: 'flex', flexDirection: 'column' } } }">
        <TabList>
          <Tab value="info">Info</Tab>
          <Tab value="bot">Bot</Tab>
          <Tab value="agents">Agents</Tab>
          <Tab value="channels">Channels</Tab>
          <Tab value="storage">Storage</Tab>
          <Tab value="tools">Tools</Tab>
          <Tab value="auth">Auth</Tab>
          <Tab value="advanced">Advanced</Tab>
        </TabList>
        <TabPanels :pt="{ root: { style: { flex: '1' } } }">
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
              <div v-for="(agent, name) in agentsConfig" :key="name" class="channel-block">
                <div class="channel-header">
                  <i class="pi pi-user"></i>
                  <strong>{{ name }}</strong>
                  <Button v-if="Object.keys(agentsConfig).length > 1" icon="pi pi-trash" severity="danger" text rounded size="small" @click="removeAgent(name)" />
                </div>
                <div class="form-group">
                  <label>Description</label>
                  <InputText v-model="agent.description" class="w-full" placeholder="What this agent specializes in" />
                </div>
                <div class="form-group">
                  <label>Model</label>
                  <InputText v-model="agent.model" class="w-full" placeholder="e.g. anthropic/claude-sonnet-4-20250514" />
                </div>
                <div class="form-group">
                  <label>Instructions</label>
                  <Textarea v-model="agent.instructions" rows="3" class="w-full" placeholder="Additional system prompt instructions for this agent" />
                </div>
                <div class="form-group">
                  <label>Tools (comma-separated, empty for all)</label>
                  <InputText v-model="agent.toolsStr" class="w-full" placeholder="tool_a, tool_b, tool_c, ..." />
                </div>
              </div>
              <div class="button-row">
                <Button label="Add Agent" icon="pi pi-plus" severity="secondary" size="small" @click="addAgent" />
                <Button label="Save" icon="pi pi-save" size="small" @click="saveAgents" />
              </div>
            </div>
          </TabPanel>

          <TabPanel value="channels" :pt="{ root: { style: { minHeight: '100%' } } }">
            <div class="tab-content">
              <div class="channel-block">
                <div class="channel-header">
                  <i class="pi pi-globe"></i>
                  <strong>Web</strong>
                  <Tag value="running" severity="success" />
                </div>
                <p class="channel-desc">Built-in web channel. Always active when the server is running.</p>
              </div>

              <div class="channel-block">
                <div class="channel-header">
                  <i class="pi pi-send"></i>
                  <strong>Telegram</strong>
                  <Tag
                    :value="channelsStore.channels?.telegram?.running ? 'running' : 'stopped'"
                    :severity="channelsStore.channels?.telegram?.running ? 'success' : 'danger'"
                  />
                </div>
                <div class="form-group">
                  <label>Bot Token</label>
                  <Password v-model="telegramToken" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                </div>
                <div class="form-group">
                  <label>Allowed Users (comma-separated)</label>
                  <InputText v-model="telegramUsers" placeholder="user1, user2" class="w-full" />
                </div>
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
              <div class="channel-block">
                <div class="channel-header">
                  <i class="pi pi-cog"></i>
                  <strong>General</strong>
                </div>
                <div class="form-group">
                  <label>Restrict to Workspace</label>
                  <ToggleSwitch v-model="tools.general.restrict_to_workspace" />
                </div>
              </div>

              <div class="channel-block">
                <div class="channel-header">
                  <i class="pi pi-code"></i>
                  <strong>Exec</strong>
                </div>
                <div class="form-group">
                  <label>Timeout (seconds)</label>
                  <InputNumber v-model="tools.exec.timeout" class="w-full" />
                </div>
              </div>

              <div class="channel-block">
                <div class="channel-header">
                  <i class="pi pi-search"></i>
                  <strong>Web Search</strong>
                </div>
                <div class="form-group">
                  <label>Brave API Key</label>
                  <Password v-model="tools.web_search.api_key" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                </div>
                <div class="form-group">
                  <label>Max Results</label>
                  <InputNumber v-model="tools.web_search.max_results" :min="1" :max="20" class="w-full" />
                </div>
              </div>

              <div class="channel-block">
                <div class="channel-header">
                  <i class="pi pi-lock"></i>
                  <strong>HTTP Auth Profiles</strong>
                </div>
                <p class="channel-desc" style="margin-bottom: 0.75rem">Authentication profiles for http_client tool (oauth1, basic, bearer).</p>

                <div v-for="(profile, name) in tools.http_client.auth_profiles" :key="name" class="auth-profile">
                  <div class="channel-header">
                    <strong>{{ name }}</strong>
                    <Select v-model="profile.type" :options="authTypes" option-label="label" option-value="value" style="width: 10rem" />
                    <Button icon="pi pi-trash" severity="danger" text rounded size="small" @click="removeAuthProfile(name)" />
                  </div>

                  <template v-if="profile.type === 'oauth1'">
                    <div class="form-group">
                      <label>Consumer Key</label>
                      <Password v-model="profile.consumer_key" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                    </div>
                    <div class="form-group">
                      <label>Consumer Secret</label>
                      <Password v-model="profile.consumer_secret" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                    </div>
                    <div class="form-group">
                      <label>Access Token</label>
                      <Password v-model="profile.access_token" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                    </div>
                    <div class="form-group">
                      <label>Access Token Secret</label>
                      <Password v-model="profile.access_token_secret" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                    </div>
                  </template>

                  <template v-if="profile.type === 'basic'">
                    <div class="form-group">
                      <label>Username</label>
                      <InputText v-model="profile.username" class="w-full" autocomplete="off" />
                    </div>
                    <div class="form-group">
                      <label>Password</label>
                      <Password v-model="profile.password" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                    </div>
                  </template>

                  <template v-if="profile.type === 'bearer'">
                    <div class="form-group">
                      <label>Token</label>
                      <Password v-model="profile.token" class="w-full" :feedback="false" toggle-mask input-class="w-full" autocomplete="off" placeholder="Leave empty to keep current" />
                    </div>
                  </template>
                </div>

                <Button label="Add Profile" icon="pi pi-plus" severity="secondary" size="small" @click="addAuthProfile" />
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
            <div class="tab-content tab-content-wide">
              <Message severity="warn" :closable="false" class="tab-message">Edit raw config with care. Invalid changes may break the application.</Message>
              <div class="form-group">
                <div class="button-row">
                  <Button label="Reload" icon="pi pi-refresh" size="small" severity="secondary" @click="loadYaml" />
                  <Button label="Validate" icon="pi pi-check-circle" size="small" severity="info" @click="validateYaml" :disabled="!rawYaml" />
                </div>
              </div>
              <div class="form-group">
                <Textarea v-model="rawYaml" rows="24" class="w-full raw-editor" auto-resize />
              </div>
              <div class="button-row">
                <Button label="Save Config" icon="pi pi-save" size="small" @click="showSaveConfirm = true" :disabled="!rawYaml" />
                <Button label="Restart Services" icon="pi pi-replay" size="small" severity="warn" :loading="restarting" @click="showRestartConfirm = true" />
              </div>
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>

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

    <Dialog v-model:visible="showAddProfile" header="Add Auth Profile" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="form-group">
        <label>Profile Name</label>
        <InputText v-model="newProfileName" class="w-full" placeholder="e.g. twitter, my_api" @keyup.enter="confirmAddProfile" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showAddProfile = false" />
        <Button label="Add" icon="pi pi-plus" size="small" @click="confirmAddProfile" :disabled="!newProfileName.trim()" />
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
  padding: 1rem;
}

.tab-content-wide {
  max-width: 800px;
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

.button-row {
  display: flex;
  gap: 0.5rem;
}

.channel-block {
  padding: 1rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  margin-bottom: 1rem;
}

.channel-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.channel-desc {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.auth-profile {
  padding: 0.75rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  margin-bottom: 0.75rem;
}

.raw-editor {
  font-family: monospace;
  font-size: 0.85rem;
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
  .form-row {
    flex-direction: column;
    gap: 0;
  }

  .tab-content {
    padding: 0.75rem;
  }
}
</style>
