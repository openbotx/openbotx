import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'

export const useTasksStore = defineStore('tasks', () => {
  const api = useApi()
  const tasks = ref(new Map())
  const activeTools = ref(new Map())

  const todoTasks = computed(() =>
    [...tasks.value.values()].filter((t) => t.state === 'TODO')
  )
  const doingTasks = computed(() =>
    [...tasks.value.values()].filter((t) => t.state === 'DOING')
  )
  const doneTasks = computed(() =>
    [...tasks.value.values()].filter((t) => t.state === 'DONE' || t.state === 'ERROR')
  )

  async function loadTasks() {
    const list = await api.get('/tasks')
    tasks.value = new Map(list.map((t) => [t.id, t]))
  }

  function onTaskCreated(data) {
    tasks.value.set(data.id, data)
  }

  function onTaskUpdated(data) {
    const existing = tasks.value.get(data.id)
    if (existing) {
      Object.assign(existing, data)
    } else {
      tasks.value.set(data.id, data)
    }
    if (data.state === 'DONE' || data.state === 'ERROR') {
      activeTools.value.delete(data.id)
    }
  }

  function onToolUse(data) {
    if (data.task_id) {
      activeTools.value.set(data.task_id, {
        tool: data.tool,
        description: data.description,
      })
    }
  }

  function onThinking(data) {
    if (data.task_id) {
      activeTools.value.set(data.task_id, { tool: null, description: 'Thinking...' })
    }
  }

  return {
    tasks, activeTools, todoTasks, doingTasks, doneTasks,
    loadTasks, onTaskCreated, onTaskUpdated, onToolUse, onThinking,
  }
})
