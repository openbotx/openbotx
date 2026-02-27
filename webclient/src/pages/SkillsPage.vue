<script setup>
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'
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

onMounted(async () => {
  try {
    skills.value = await api.get('/skills')
  } finally {
    loading.value = false
  }
})

async function viewSkill(skill) {
  const data = await api.get(`/skills/${skill.name}`)
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
    const result = await api.put(`/skills/${selectedSkill.value.name}`, { content: editContent.value })
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
</script>

<template>
  <div class="skills-page">
    <div class="page-header">
      <h2>Skills</h2>
    </div>

    <div v-if="loading" class="page-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
    </div>

    <div v-else-if="skills.length" class="skills-grid">
      <Card v-for="skill in skills" :key="skill.name" class="skill-card" @click="viewSkill(skill)">
        <template #title>
          <div class="skill-header">
            <div class="skill-name">
              <i class="pi pi-bolt"></i>
              {{ skill.name }}
            </div>
            <div class="skill-tags">
              <Tag v-if="skill.always" value="always active" severity="info" />
              <Tag :value="skill.source === 'builtin' ? 'builtin' : 'project'" :severity="skill.source === 'builtin' ? 'secondary' : 'success'" />
            </div>
          </div>
        </template>
        <template #subtitle>
          {{ skill.description }}
        </template>
      </Card>
    </div>

    <div v-else class="empty-state">
      <i class="pi pi-bolt" style="font-size: 2.5rem"></i>
      <p>No skills found</p>
    </div>

    <Dialog
      v-model:visible="dialogVisible"
      modal
      maximizable
      :style="{ width: '80vw', maxWidth: '800px' }"
      :breakpoints="{ '768px': '95vw' }"
    >
      <template #header>
        <div class="dialog-header">
          <span class="dialog-title">{{ selectedSkill?.name }}</span>
          <div v-if="selectedSkill?.source === 'project'" class="dialog-actions">
            <Button v-if="!editing" icon="pi pi-pencil" label="Edit" severity="secondary" size="small" @click="startEdit" />
            <template v-else>
              <Button icon="pi pi-times" label="Cancel" severity="secondary" size="small" @click="cancelEdit" />
              <Button icon="pi pi-check" label="Save" size="small" :loading="saving" @click="saveSkill" />
            </template>
          </div>
        </div>
      </template>

      <Textarea
        v-if="editing"
        v-model="editContent"
        class="skill-editor"
        autoResize
        :style="{ width: '100%', minHeight: '400px', fontFamily: 'ui-monospace, monospace', fontSize: '0.85rem' }"
      />
      <MdPreview v-else :modelValue="skillContent || ''" :theme="isDark ? 'dark' : 'light'" codeTheme="github" :codeStyleReverse="false" language="en-US" class="skill-content" />
    </Dialog>
  </div>
</template>

<style scoped>
.skills-page {
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
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 1rem;
}

.dialog-title {
  font-weight: 700;
}

.dialog-actions {
  display: flex;
  gap: 0.5rem;
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
