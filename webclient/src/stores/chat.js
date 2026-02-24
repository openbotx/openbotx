import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'

export const useChatStore = defineStore('chat', () => {
  const api = useApi()
  const messages = ref([])
  const sessions = ref([])
  const currentSessionId = ref('direct')
  const streaming = ref(false)
  const currentToolUse = ref(null)

  async function sendMessage(text) {
    messages.value.push({ role: 'user', content: text, timestamp: Date.now() })
    streaming.value = true
    currentToolUse.value = null

    try {
      const res = await api.post('/chat', {
        message: text,
        session_id: currentSessionId.value,
      })
      return res
    } catch (e) {
      streaming.value = false
      throw e
    }
  }

  function onMessage(data) {
    streaming.value = false
    currentToolUse.value = null
    messages.value.push({
      role: 'assistant',
      content: data.content,
      task_id: data.task_id,
      timestamp: Date.now(),
    })
  }

  function onThinking(data) {
    streaming.value = true
  }

  function onToolUse(data) {
    currentToolUse.value = {
      tool: data.tool,
      arguments: data.arguments,
      result: data.result,
    }
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant' && last.tool_uses) {
      last.tool_uses.push(data)
    } else if (!last || last.role !== 'assistant') {
      messages.value.push({
        role: 'assistant',
        content: '',
        tool_uses: [data],
        timestamp: Date.now(),
      })
    }
  }

  async function loadSessions() {
    sessions.value = await api.get('/chat/sessions')
  }

  async function loadHistory(sessionId) {
    const data = await api.get(`/chat/sessions/${sessionId}`)
    messages.value = (data.messages || []).map((m) => ({
      ...m,
      timestamp: Date.now(),
    }))
    currentSessionId.value = sessionId
  }

  async function clearSession(sessionId) {
    await api.del(`/chat/sessions/${sessionId}`)
    if (sessionId === currentSessionId.value) {
      messages.value = []
    }
  }

  function newSession() {
    currentSessionId.value = 'session_' + Date.now()
    messages.value = []
    streaming.value = false
    currentToolUse.value = null
  }

  return {
    messages,
    sessions,
    currentSessionId,
    streaming,
    currentToolUse,
    sendMessage,
    onMessage,
    onThinking,
    onToolUse,
    loadSessions,
    loadHistory,
    clearSession,
    newSession,
  }
})
