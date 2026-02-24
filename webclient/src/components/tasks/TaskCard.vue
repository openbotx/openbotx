<script setup>
import Tag from 'primevue/tag'

const props = defineProps({
  task: { type: Object, required: true },
})

const severityMap = {
  TODO: 'info',
  DOING: 'warn',
  DONE: 'success',
  ERROR: 'danger',
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="task-card">
    <div class="task-header">
      <span class="task-title">{{ task.title }}</span>
      <Tag :value="task.state" :severity="severityMap[task.state] || 'secondary'" />
    </div>
    <div v-if="task.description" class="task-desc">
      {{ task.description.substring(0, 120) }}
    </div>
    <div class="task-meta">
      <span v-if="task.agent_type === 'subagent'" class="agent-badge">
        <i class="pi pi-sitemap"></i> subagent
      </span>
      <span class="task-time">{{ formatTime(task.created_at) }}</span>
    </div>
  </div>
</template>

<style scoped>
.task-card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.5rem;
  padding: 0.75rem;
  overflow-wrap: break-word;
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.task-title {
  font-weight: 600;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.task-desc {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  margin-bottom: 0.4rem;
  line-height: 1.4;
}

.task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

.agent-badge {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  background: var(--p-surface-200);
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
}
</style>
