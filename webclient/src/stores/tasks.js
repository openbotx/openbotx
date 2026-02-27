import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'

export const useTasksStore = defineStore('tasks', () => {
  const api = useApi()
  const tasks = ref({})
  const activeTools = ref({})
  const selectedAgent = ref('')

  function sortByNewest(list) {
    return list.slice().sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''))
  }

  const filteredTasks = computed(() => {
    const all = Object.values(tasks.value)
    if (!selectedAgent.value) return all
    return all.filter((t) => t.agent_name === selectedAgent.value)
  })

  const todoTasks = computed(() =>
    sortByNewest(filteredTasks.value.filter((t) => t.state === 'TODO'))
  )
  const doingTasks = computed(() =>
    sortByNewest(filteredTasks.value.filter((t) => t.state === 'DOING'))
  )
  const doneTasks = computed(() =>
    sortByNewest(filteredTasks.value.filter((t) => t.state === 'DONE' || t.state === 'ERROR'))
  )

  async function loadTasks() {
    const list = await api.get('/tasks')
    const fresh = {}
    for (const t of list) {
      fresh[t.id] = t
    }
    // Preserve in-flight tasks from WebSocket that the API response may not include yet
    for (const [id, existing] of Object.entries(tasks.value)) {
      if (!fresh[id] && (existing.state === 'DOING' || existing.state === 'TODO')) {
        fresh[id] = existing
      }
    }
    tasks.value = fresh

    const tools = {}
    for (const t of Object.values(fresh)) {
      const toolUses = t.live_state?.tool_uses
      if (t.state === 'DOING' && toolUses?.length) {
        const last = toolUses[toolUses.length - 1]
        tools[t.id] = { tool: last.tool, description: last.description }
      }
    }
    activeTools.value = tools
  }

  function onTaskCreated(data) {
    tasks.value = { ...tasks.value, [data.id]: data }
  }

  function onTaskUpdated(data) {
    const existing = tasks.value[data.id]
    const updated = existing ? { ...existing, ...data } : data
    tasks.value = { ...tasks.value, [data.id]: updated }
    if (data.state === 'DONE' || data.state === 'ERROR') {
      const { [data.id]: _, ...rest } = activeTools.value
      activeTools.value = rest
    }
  }

  function onToolUse(data) {
    if (data.task_id) {
      activeTools.value = {
        ...activeTools.value,
        [data.task_id]: { tool: data.tool, description: data.description },
      }
    }
  }

  function onThinking(data) {
    if (data.task_id) {
      activeTools.value = {
        ...activeTools.value,
        [data.task_id]: { tool: null, description: 'Thinking...' },
      }
    }
  }

  return {
    tasks, activeTools, selectedAgent, todoTasks, doingTasks, doneTasks,
    loadTasks, onTaskCreated, onTaskUpdated, onToolUse, onThinking,
  }
})
