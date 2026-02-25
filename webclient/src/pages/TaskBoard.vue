<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import TaskColumn from '../components/tasks/TaskColumn.vue'
import { useTasksStore } from '../stores/tasks'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const tasksStore = useTasksStore()
const chatStore = useChatStore()

const showConfirm = ref(false)
const targetTask = ref(null)

onMounted(() => {
  tasksStore.loadTasks()
})

function handleGoToSession(task) {
  targetTask.value = task
  showConfirm.value = true
}

async function confirmGoToSession() {
  showConfirm.value = false
  const t = targetTask.value
  if (!t) return
  const sessionKey = `${t.channel}:${t.chat_id}`
  await chatStore.switchSession(sessionKey)
  router.push({ name: 'chat' })
}
</script>

<template>
  <div class="task-board">
    <div class="board-header">
      <h2>Task Board</h2>
    </div>
    <div class="board-columns">
      <TaskColumn title="TODO" :tasks="tasksStore.todoTasks" @go-to-session="handleGoToSession" />
      <TaskColumn title="DOING" :tasks="tasksStore.doingTasks" @go-to-session="handleGoToSession" />
      <TaskColumn title="DONE" :tasks="tasksStore.doneTasks" @go-to-session="handleGoToSession" />
    </div>

    <Dialog v-model:visible="showConfirm" header="Open Session" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <p>Open chat session for <strong>{{ targetTask?.title }}</strong>?</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showConfirm = false" />
        <Button label="Open" icon="pi pi-comments" size="small" @click="confirmGoToSession" />
      </template>
    </Dialog>
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
