<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import TaskColumn from '../components/tasks/TaskColumn.vue'
import { useTasksStore } from '../stores/tasks'
import { useChatStore } from '../stores/chat'
import { useAgentsStore } from '../stores/agents'

const router = useRouter()
const tasksStore = useTasksStore()
const chatStore = useChatStore()
const agentsStore = useAgentsStore()

const showConfirm = ref(false)
const targetTask = ref(null)
const loading = ref(true)

const agentOptions = computed(() =>
  agentsStore.agents.map((a) => ({ label: a.name, value: a.name }))
)

onMounted(async () => {
  try {
    await Promise.all([tasksStore.loadTasks(), agentsStore.loadAgents()])
  } finally {
    loading.value = false
  }
})

function handleGoToSession(task) {
  targetTask.value = task
  showConfirm.value = true
}

async function confirmGoToSession() {
  showConfirm.value = false
  const t = targetTask.value
  if (!t || !t.channel || !t.chat_id) return
  const sessionKey = `${t.channel}:${t.chat_id}`
  await chatStore.switchSession(sessionKey)
  router.push({ name: 'chat' })
}
</script>

<template>
  <div class="task-board">
    <div class="board-header">
      <h2>Task Board</h2>
      <Select
        v-if="agentsStore.agents.length > 1"
        v-model="tasksStore.selectedAgent"
        :options="agentOptions"
        option-label="label"
        option-value="value"
        placeholder="All agents"
        :show-clear="true"
        class="agent-filter"
      />
    </div>
    <div v-if="loading" class="page-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
    </div>
    <div v-else class="board-columns">
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.board-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.agent-filter {
  width: 12rem;
}

.page-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--p-text-muted-color);
}

.board-columns {
  flex: 1;
  display: flex;
  overflow-x: auto;
}

@media (max-width: 768px) {
  .board-header {
    padding: 0.5rem 0.75rem;
  }

  .board-columns {
    flex-direction: column;
    overflow-x: visible;
    overflow-y: auto;
  }
}
</style>
