<script setup>
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'
import { useApi } from '../composables/useApi'

const api = useApi()
const skills = ref([])
const selectedSkill = ref(null)
const skillContent = ref('')
const dialogVisible = ref(false)

onMounted(async () => {
  skills.value = await api.get('/skills')
})

async function viewSkill(skill) {
  const data = await api.get(`/skills/${skill.name}`)
  selectedSkill.value = skill
  skillContent.value = data.content
  dialogVisible.value = true
}
</script>

<template>
  <div class="skills-page">
    <div class="page-header">
      <h2>Skills</h2>
    </div>

    <div v-if="skills.length" class="skills-grid">
      <Card v-for="skill in skills" :key="skill.name" class="skill-card" @click="viewSkill(skill)">
        <template #title>
          <div class="skill-title">
            <i class="pi pi-bolt"></i>
            {{ skill.name }}
            <Tag v-if="skill.always" value="always active" severity="info" />
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
      :header="selectedSkill?.name"
      modal
      maximizable
      :style="{ width: '80vw', maxWidth: '800px' }"
      :breakpoints="{ '768px': '95vw' }"
    >
      <MdPreview :modelValue="skillContent || ''" class="skill-content" />
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
  gap: 1rem;
  padding: 1rem;
}

.skill-card {
  cursor: pointer;
}

.skill-title {
  display: flex;
  align-items: center;
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
