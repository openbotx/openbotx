<script setup>
import TaskCard from './TaskCard.vue'

defineProps({
  title: { type: String, required: true },
  tasks: { type: Array, default: () => [] },
  severity: { type: String, default: 'info' },
})

const emit = defineEmits(['go-to-session'])
</script>

<template>
  <div class="task-column">
    <div class="column-header">
      <span class="column-title">{{ title }}</span>
      <span class="column-count">{{ tasks.length }}</span>
    </div>
    <div class="column-cards">
      <TaskCard v-for="task in tasks" :key="task.id" :task="task" @go-to-session="emit('go-to-session', $event)" />
      <div v-if="tasks.length === 0" class="empty-column">
        No tasks
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-column {
  flex: 1;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  max-height: 100%;
  border-right: 1px solid var(--p-content-border-color);
}

.task-column:last-child {
  border-right: none;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.75rem;
  font-weight: 600;
  border-bottom: 1px solid var(--p-content-border-color);
}

.column-count {
  background: color-mix(in srgb, var(--p-text-color) 10%, transparent);
  color: var(--p-text-muted-color);
  border-radius: 1rem;
  padding: 0.15rem 0.6rem;
  font-size: 0.8rem;
}

.column-cards {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.empty-column {
  text-align: center;
  color: var(--p-text-muted-color);
  padding: 2rem 0;
  font-size: 0.85rem;
}

@media (max-width: 768px) {
  .task-column {
    min-width: 0;
    border-right: none;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  .task-column:last-child {
    border-bottom: none;
  }

  .column-cards {
    overflow-y: visible;
  }

  .empty-column {
    padding: 1rem 0;
  }
}
</style>
