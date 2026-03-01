<script setup>
import { ref, watch, onMounted } from 'vue'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { useApi } from '../composables/useApi'
import { useToast } from 'primevue/usetoast'
import { useDark } from '../composables/useDark'

const MARKETPLACE_URL = 'https://openbotx-marketplace.pages.dev/skills/index.json'

const api = useApi()
const toast = useToast()
const isDark = useDark()

const allSkills = ref([])
const search = ref('')
const loading = ref(true)
const installing = ref(null)

const readDialogVisible = ref(false)
const readContent = ref('')
const readTitle = ref('')

const licenseDialogVisible = ref(false)
const licenseContent = ref('')
const licenseTitle = ref('')
const licenseLoading = ref(false)

const confirmDialogVisible = ref(false)
const confirmTarget = ref(null)
const confirmReplace = ref(false)
const confirmChecking = ref(false)

const targets = ref([])
const selectedTarget = ref('')

const PAGE_SIZE = 24

const allMatches = ref([])
const displayedSkills = ref([])
const searching = ref(false)
let searchTimer = null

function runFilter(q) {
  if (!q) {
    allMatches.value = []
    displayedSkills.value = []
    return
  }
  const nameMatches = []
  const descMatches = []
  const seen = new Set()
  for (const skill of allSkills.value) {
    const key = `${skill.source}/${skill.name}`
    if (seen.has(key)) continue
    seen.add(key)
    if (skill.name.toLowerCase().includes(q)) {
      nameMatches.push(skill)
    } else if (skill.description.toLowerCase().includes(q)) {
      descMatches.push(skill)
    }
  }
  allMatches.value = [...nameMatches, ...descMatches]
  displayedSkills.value = allMatches.value.slice(0, PAGE_SIZE)
}

function loadMore() {
  const next = displayedSkills.value.length + PAGE_SIZE
  displayedSkills.value = allMatches.value.slice(0, next)
}

watch(search, (val) => {
  clearTimeout(searchTimer)
  const q = val.trim().toLowerCase()
  if (!q) {
    searching.value = false
    allMatches.value = []
    displayedSkills.value = []
    return
  }
  searching.value = true
  searchTimer = setTimeout(() => {
    runFilter(q)
    searching.value = false
  }, 300)
})

onMounted(() => Promise.all([loadCatalog(), loadTargets()]))

async function loadCatalog() {
  loading.value = true
  try {
    const res = await fetch(MARKETPLACE_URL)
    const data = await res.json()
    allSkills.value = Array.isArray(data) ? data : data.skills || []
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to load marketplace catalog', life: 3000 })
    allSkills.value = []
  } finally {
    loading.value = false
  }
}

async function loadTargets() {
  try {
    targets.value = await api.get('/marketplace/targets')
    if (targets.value.length) selectedTarget.value = targets.value[0].value
  } catch {
    targets.value = [{ label: 'Project', value: '' }]
  }
}

function refresh() {
  search.value = ''
  loadCatalog()
}

function clearSearch() {
  search.value = ''
}

async function viewReadme(skill) {
  readTitle.value = skill.name
  readContent.value = ''
  readDialogVisible.value = true
  try {
    const res = await fetch(skill['readme-url'])
    readContent.value = await res.text()
  } catch {
    readContent.value = '> Failed to load skill readme.'
  }
}

async function viewLicense(skill) {
  licenseTitle.value = `${skill.name} — License`
  licenseContent.value = ''
  licenseLoading.value = true
  licenseDialogVisible.value = true
  try {
    const res = await fetch(skill.license)
    licenseContent.value = await res.text()
  } catch {
    licenseContent.value = 'Failed to load license.'
  } finally {
    licenseLoading.value = false
  }
}

async function handleInstall(skill) {
  confirmTarget.value = skill
  confirmReplace.value = false
  selectedTarget.value = targets.value.length ? targets.value[0].value : ''
  confirmDialogVisible.value = true
}

watch(selectedTarget, () => {
  // reset replace state when user changes target
  if (confirmDialogVisible.value) confirmReplace.value = false
})

async function confirmInstall() {
  const skill = confirmTarget.value
  if (!skill) return

  // first click: check if already installed
  if (!confirmReplace.value) {
    confirmChecking.value = true
    try {
      const agent = selectedTarget.value || ''
      const check = await api.get(`/marketplace/check/${skill.source}/${skill.name}?agent=${encodeURIComponent(agent)}`)
      if (check.installed) {
        confirmReplace.value = true
        return
      }
    } catch (e) {
      toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
      return
    } finally {
      confirmChecking.value = false
    }
  }

  // proceed with install
  installing.value = skill.name
  confirmDialogVisible.value = false
  confirmReplace.value = false
  try {
    await doInstall(skill)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  } finally {
    installing.value = null
  }
}

async function doInstall(skill) {
  const agent = selectedTarget.value || ''
  const result = await api.post('/marketplace/install', { source: skill.source, name: skill.name, agent })
  if (result.error) {
    toast.add({ severity: 'error', summary: 'Error', detail: result.error, life: 3000 })
    return
  }
  const target = targets.value.find(t => t.value === agent)
  const label = target ? target.label : 'project'
  toast.add({ severity: 'success', summary: 'Installed', detail: `${skill.name} → ${label}`, life: 2000 })
}
</script>

<template>
  <div class="marketplace-page">
    <div class="page-header">
      <h2>Marketplace</h2>
      <div class="header-actions">
        <Button icon="pi pi-refresh" severity="secondary" text size="small" title="Refresh" @click="refresh" />
      </div>
    </div>

    <div class="search-bar">
      <span class="p-input-icon-left search-input-wrapper">
        <i class="pi pi-search" />
        <InputText v-model="search" placeholder="Search skills..." class="search-input" />
      </span>
      <i v-if="searching" class="pi pi-spin pi-spinner search-spinner" />
      <span v-if="!loading && !searching && search" class="search-count">{{ allMatches.length }} / {{ allSkills.length }} skills</span>
      <Button v-if="search" icon="pi pi-times" severity="secondary" text size="small" @click="clearSearch" title="Clear search" />
    </div>

    <div v-if="loading" class="page-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
    </div>

    <div v-else-if="!search" class="empty-state">
      <i class="pi pi-shop" style="font-size: 2.5rem"></i>
      <p>Search for a skill by name or description</p>
    </div>

    <div v-else-if="displayedSkills.length" class="marketplace-grid">
      <Card v-for="skill in displayedSkills" :key="`${skill.source}/${skill.name}`" class="marketplace-card">
        <template #title>
          <div class="card-name">
            <i class="pi pi-bolt"></i>
            {{ skill.name }}
          </div>
        </template>
        <template #subtitle>
          <Tag :value="skill.source" severity="secondary" class="card-source" />
          <div>{{ skill.description }}</div>
        </template>
        <template #footer>
          <div class="card-actions">
            <Button
              icon="pi pi-download"
              label="Install"
              size="small"
              :loading="installing === skill.name"
              @click="handleInstall(skill)"
            />
            <Button icon="pi pi-book" label="Read" severity="secondary" text size="small" @click="viewReadme(skill)" />
            <Button v-if="skill.license" icon="pi pi-file" label="License" severity="secondary" text size="small" @click="viewLicense(skill)" />
          </div>
        </template>
      </Card>
      <div v-if="allMatches.length > displayedSkills.length" class="more-results">
        <Button label="Load more" icon="pi pi-angle-down" severity="secondary" text size="small" @click="loadMore" />
        <span>{{ displayedSkills.length }} of {{ allMatches.length }}</span>
      </div>
    </div>

    <div v-else class="empty-state">
      <i class="pi pi-search" style="font-size: 2.5rem"></i>
      <p>No skills matching "{{ search }}"</p>
    </div>

    <Dialog
      v-model:visible="readDialogVisible"
      modal
      maximizable
      :style="{ width: '80vw', maxWidth: '800px' }"
      :breakpoints="{ '768px': '95vw' }"
    >
      <template #header>
        <span class="dialog-title">{{ readTitle }}</span>
      </template>
      <div v-if="!readContent" class="dialog-loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
      </div>
      <MdPreview v-else :modelValue="readContent" :theme="isDark ? 'dark' : 'light'" codeTheme="github" :codeStyleReverse="false" language="en-US" class="readme-content" />
    </Dialog>

    <Dialog
      v-model:visible="licenseDialogVisible"
      modal
      maximizable
      :style="{ width: '80vw', maxWidth: '700px' }"
      :breakpoints="{ '768px': '95vw' }"
    >
      <template #header>
        <span class="dialog-title">{{ licenseTitle }}</span>
      </template>
      <div v-if="licenseLoading" class="dialog-loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
      </div>
      <pre v-else class="license-text">{{ licenseContent }}</pre>
    </Dialog>

    <Dialog v-model:visible="confirmDialogVisible" :header="confirmReplace ? 'Replace Skill' : 'Install Skill'" :modal="true" :style="{ width: '26rem' }" :breakpoints="{ '768px': '90vw' }">
      <div class="install-dialog">
        <p v-if="confirmReplace">
          <strong>{{ confirmTarget?.source }}/{{ confirmTarget?.name }}</strong> is already installed. Replace it?
        </p>
        <p v-else>Install <strong>{{ confirmTarget?.source }}/{{ confirmTarget?.name }}</strong>?</p>
        <div v-if="targets.length > 1 && !confirmReplace" class="install-target">
          <label>Install to</label>
          <Select
            v-model="selectedTarget"
            :options="targets"
            option-label="label"
            option-value="value"
            class="install-target-select"
          />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="confirmDialogVisible = false" />
        <Button
          :label="confirmReplace ? 'Replace' : 'Install'"
          :icon="confirmReplace ? 'pi pi-refresh' : 'pi pi-download'"
          :severity="confirmReplace ? 'warn' : undefined"
          :loading="confirmChecking"
          size="small"
          @click="confirmInstall"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.marketplace-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.page-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.header-actions {
  display: flex;
  gap: 0.25rem;
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

.search-spinner {
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.search-count {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.marketplace-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.75rem;
  padding: 0.75rem;
  align-content: start;
}

.marketplace-card {
  display: flex;
  flex-direction: column;
}

.card-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  word-break: break-word;
}

.card-source {
  margin-bottom: 0.35rem;
  font-size: 0.65rem;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.dialog-title {
  font-weight: 700;
}

.more-results {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

.install-dialog p {
  margin: 0 0 0.75rem;
}

.install-target {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.install-target label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-text-muted-color);
}

.install-target-select {
  width: 100%;
  font-size: 0.85rem;
}

.dialog-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--p-text-muted-color);
}

.readme-content {
  line-height: 1.7;
}

.readme-content :deep(pre) {
  background: var(--p-surface-100);
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.85rem;
}

.readme-content :deep(code) {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
}

.license-text {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  margin: 0;
  color: var(--p-text-color);
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

@media (max-width: 768px) {
  .marketplace-grid {
    grid-template-columns: 1fr;
  }

  .search-bar {
    padding: 0.5rem 0.75rem;
  }
}
</style>
