<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { useApi } from '../composables/useApi'
import { useToast } from 'primevue/usetoast'
import { useDark } from '../composables/useDark'

const api = useApi()
const toast = useToast()
const isDark = useDark()
const skills = ref([])
const selectedSkill = ref(null)
const skillContent = ref('')
const dialogVisible = ref(false)
const editing = ref(false)
const editContent = ref('')
const saving = ref(false)
const loading = ref(true)
const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

const search = ref('')
const targets = ref([])
const selectedTarget = ref(null)

const filteredSkills = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return skills.value
  return skills.value.filter(s =>
    s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
  )
})

function agentQuery(agent) {
  return agent ? `?agent=${encodeURIComponent(agent)}` : ''
}

async function loadTargets() {
  try {
    const data = await api.get('/marketplace/targets')
    targets.value = [{ label: 'All', value: null }, ...data]
  } catch {
    targets.value = [{ label: 'All', value: null }]
  }
}

async function loadSkills() {
  loading.value = true
  try {
    const agent = selectedTarget.value
    const query = agent === null ? '' : `?agent=${encodeURIComponent(agent)}`
    skills.value = await api.get(`/skills${query}`)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadTargets()
  await loadSkills()
})

watch(selectedTarget, () => loadSkills())

async function viewSkill(skill) {
  const data = await api.get(`/skills/${skill.name}${agentQuery(skill.agent)}`)
  selectedSkill.value = { ...skill, source: data.source }
  skillContent.value = data.content
  editing.value = false
  dialogVisible.value = true
}

function startEdit() {
  editContent.value = skillContent.value
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveSkill() {
  saving.value = true
  try {
    const skill = selectedSkill.value
    const result = await api.put(`/skills/${skill.name}${agentQuery(skill.agent)}`, { content: editContent.value })
    if (result.error) {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error, life: 3000 })
      return
    }
    skillContent.value = editContent.value
    editing.value = false
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Skill updated', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  } finally {
    saving.value = false
  }
}

function promptDelete(skill, event) {
  event.stopPropagation()
  deleteTarget.value = skill
  showDeleteConfirm.value = true
}

async function confirmDelete() {
  showDeleteConfirm.value = false
  const skill = deleteTarget.value
  if (!skill) return
  try {
    const result = await api.del(`/skills/${skill.name}${agentQuery(skill.agent)}`)
    if (result.error) {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error, life: 3000 })
      return
    }
    toast.add({ severity: 'success', summary: 'Deleted', detail: `${skill.name} removed`, life: 2000 })
    await loadSkills()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: e.message, life: 3000 })
  }
}

function deleteLocation(skill) {
  if (skill?.agent) return `agent: ${skill.agent}`
  if (skill?.source === 'project') return 'project'
  return ''
}
</script>

<template>
  <div class="skills-page">
    <div class="page-header">
      <h2>Skills</h2>
      <Select
        v-if="targets.length > 2"
        v-model="selectedTarget"
        :options="targets"
        option-label="label"
        option-value="value"
        placeholder="Filter by agent..."
        class="target-select"
      />
    </div>

    <div class="search-bar">
      <span class="p-input-icon-left search-input-wrapper">
        <i class="pi pi-search" />
        <InputText v-model="search" placeholder="Search skills..." class="search-input" />
      </span>
      <span v-if="!loading" class="search-count">{{ filteredSkills.length }} skills</span>
    </div>

    <div v-if="loading" class="page-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
    </div>

    <div v-else-if="filteredSkills.length" class="skills-grid">
      <Card v-for="skill in filteredSkills" :key="`${skill.name}:${skill.agent}`" class="skill-card" @click="viewSkill(skill)">
        <template #title>
          <div class="skill-header">
            <div class="skill-name">
              <i class="pi pi-bolt"></i>
              {{ skill.name.split('/').pop() }}
            </div>
            <div class="skill-tags">
              <Tag :value="skill.agent ? `agent: ${skill.agent}` : skill.source" severity="contrast" class="skill-tag" />
              <Tag v-if="skill.publisher" :value="skill.publisher" severity="secondary" class="skill-tag" />
              <Tag v-if="skill.always" value="always active" severity="info" class="skill-tag" />
            </div>
          </div>
        </template>
        <template #subtitle>
          {{ skill.description }}
        </template>
        <template #footer>
          <div class="skill-footer">
            <Button
              v-if="skill.source !== 'builtin'"
              icon="pi pi-trash"
              severity="danger"
              text
              size="small"
              title="Delete skill"
              @click="promptDelete(skill, $event)"
            />
          </div>
        </template>
      </Card>
    </div>

    <div v-else class="empty-state">
      <i class="pi pi-bolt" style="font-size: 2.5rem"></i>
      <p v-if="search">No skills matching "{{ search }}"</p>
      <p v-else>No skills found</p>
    </div>

    <Dialog
      v-model:visible="dialogVisible"
      modal
      maximizable
      :style="{ width: '80vw', maxWidth: '800px' }"
      :breakpoints="{ '768px': '95vw' }"
    >
      <template #header>
        <span class="dialog-title">{{ selectedSkill?.name?.split('/').pop() }}</span>
      </template>

      <div v-if="selectedSkill?.source !== 'builtin'" class="editor-toolbar">
        <span class="editor-path">{{ selectedSkill?.name }}</span>
        <div class="editor-actions">
          <Button
            v-if="!editing"
            icon="pi pi-pencil"
            label="Edit"
            severity="secondary"
            text
            size="small"
            @click="startEdit"
          />
          <template v-else>
            <Button icon="pi pi-times" label="Cancel" severity="secondary" text size="small" @click="cancelEdit" />
            <Button icon="pi pi-save" label="Save" size="small" :loading="saving" @click="saveSkill" />
          </template>
        </div>
      </div>

      <MdEditor
        v-if="editing"
        v-model="editContent"
        :theme="isDark ? 'dark' : 'light'"
        codeTheme="github"
        :codeStyleReverse="false"
        language="en-US"
        :preview="false"
        :toolbars="['bold', 'underline', 'italic', 'strikeThrough', '-',
          'title', 'sub', 'sup', 'quote', 'unorderedList', 'orderedList', 'task', '-',
          'codeRow', 'code', 'link', 'image', 'table', '-',
          'revoke', 'next', '=',
          'preview', 'fullscreen']"
        class="skill-md-editor"
      />
      <MdPreview v-else :modelValue="skillContent || ''" :theme="isDark ? 'dark' : 'light'" codeTheme="github" :codeStyleReverse="false" language="en-US" class="skill-content" />
    </Dialog>

    <Dialog v-model:visible="showDeleteConfirm" header="Delete Skill" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <p>Delete <strong>{{ deleteTarget?.name }}</strong> from <strong>{{ deleteLocation(deleteTarget) }}</strong>?</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showDeleteConfirm = false" />
        <Button label="Delete" icon="pi pi-trash" severity="danger" size="small" @click="confirmDelete" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.skills-page {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.page-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.target-select {
  min-width: 10rem;
  font-size: 0.85rem;
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

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.75rem;
  padding: 0.75rem;
}

.skill-card {
  cursor: pointer;
}

.skill-header {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.skill-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.skill-tags {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.skill-tag {
  font-size: 0.65rem;
}

.skill-footer {
  display: flex;
  justify-content: flex-end;
}

.dialog-title {
  font-weight: 700;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.editor-path {
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.editor-actions {
  display: flex;
  gap: 0.5rem;
}

.skill-md-editor {
  min-height: 400px;
}

.skill-content {
  line-height: 1.7;
}

.skill-content :deep(pre) {
  background: var(--p-surface-100);
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.85rem;
}

.skill-content :deep(code) {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
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
