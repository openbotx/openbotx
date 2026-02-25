import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'

/**
 * Extract the chat_id from a session key.
 * "web:abc-123" → "abc-123", "heartbeat:heartbeat" → "heartbeat"
 */
function chatIdFromKey(key) {
  const idx = key.indexOf(':')
  return idx !== -1 ? key.slice(idx + 1) : key
}

/**
 * Extract the channel from a session key.
 * "web:abc-123" → "web", "heartbeat:heartbeat" → "heartbeat"
 */
function channelFromKey(key) {
  const idx = key.indexOf(':')
  return idx !== -1 ? key.slice(0, idx) : key
}

/**
 * Display label for a session key.
 */
function sessionLabel(key) {
  const channel = channelFromKey(key)
  const chatId = chatIdFromKey(key)

  if (channel === 'heartbeat') return 'Heartbeat'
  if (channel === 'telegram') return `Telegram ${chatId}`
  if (channel === 'web') {
    return chatId.length > 12 ? `Chat ${chatId.slice(0, 8)}` : chatId
  }
  return key
}

export { chatIdFromKey, channelFromKey, sessionLabel }

export const useChatStore = defineStore('chat', () => {
  const api = useApi()
  const messages = ref([])
  const sessions = ref([])
  let stored = localStorage.getItem('chat_session')
  // Migrate bare UUIDs from older versions to full session keys
  if (stored && !stored.includes(':')) {
    stored = `web:${stored}`
    localStorage.setItem('chat_session', stored)
  }
  const currentSessionId = ref(stored || `web:${crypto.randomUUID()}`)
  if (!stored) localStorage.setItem('chat_session', currentSessionId.value)
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

  function _isCurrentSession(data) {
    if (!data.chat_id) return true
    return data.chat_id === chatIdFromKey(currentSessionId.value)
  }

  function onMessage(data) {
    if (!_isCurrentSession(data)) return
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
    if (!_isCurrentSession(data)) return
    streaming.value = true
  }

  function onToolUse(data) {
    if (!_isCurrentSession(data)) return
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

  async function loadHistory(sessionKey) {
    const data = await api.get(`/chat/sessions/${sessionKey}`)
    messages.value = (data.messages || []).map((m) => ({
      ...m,
      timestamp: Date.now(),
    }))
    currentSessionId.value = sessionKey
    localStorage.setItem('chat_session', sessionKey)
  }

  async function switchSession(sessionKey) {
    streaming.value = false
    currentToolUse.value = null
    await loadHistory(sessionKey)
    await loadSessions()
  }

  async function clearSession(sessionKey) {
    await api.del(`/chat/sessions/${sessionKey}`)
    if (sessionKey === currentSessionId.value) {
      messages.value = []
    }
    await loadSessions()
  }

  function onSessionsUpdated() {
    loadSessions()
  }

  function newSession() {
    const key = `web:${crypto.randomUUID()}`
    currentSessionId.value = key
    localStorage.setItem('chat_session', key)
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
    onSessionsUpdated,
    loadSessions,
    loadHistory,
    switchSession,
    clearSession,
    newSession,
  }
})
