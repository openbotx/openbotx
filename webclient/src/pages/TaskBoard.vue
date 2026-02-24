<script setup>
import { onMounted } from 'vue'
import TaskColumn from '../components/tasks/TaskColumn.vue'
import { useTasksStore } from '../stores/tasks'

const tasksStore = useTasksStore()

onMounted(() => {
  tasksStore.loadTasks()
})
</script>

<template>
  <div class="task-board">
    <div class="board-header">
      <h2>Task Board</h2>
    </div>
    <div class="board-columns">
      <TaskColumn title="TODO" :tasks="tasksStore.todoTasks" />
      <TaskColumn title="DOING" :tasks="tasksStore.doingTasks" />
      <TaskColumn title="DONE" :tasks="tasksStore.doneTasks" />
    </div>
  </div>
</template>

<style scoped>
.task-board {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.board-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.board-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.board-columns {
  flex: 1;
  display: flex;
  gap: 1rem;
  padding: 1rem;
  overflow-x: auto;
}

@media (max-width: 768px) {
  .board-columns {
    padding: 0.5rem;
    gap: 0.5rem;
  }

  .board-header {
    padding: 0.5rem 0.75rem;
  }
}
</style>
