import { defineStore } from 'pinia'
import { ref } from 'vue'
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
  if (channel === 'cron') return `Cron ${chatId}`
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
  // migrate bare UUIDs from older versions to full session keys
  if (stored && !stored.includes(':')) {
    stored = `web:${stored}`
    localStorage.setItem('chat_session', stored)
  }
  const currentSessionId = ref(stored || `web:${crypto.randomUUID()}`)
  if (!stored) localStorage.setItem('chat_session', currentSessionId.value)

  const liveMessage = ref(null)
  const toolRunning = ref(false)

  // per-session live state cache — websocket events always update their
  // session's entry regardless of which session the user is viewing.
  // the refs above are a reactive "view" into the current session's cache.
  const _liveCache = new Map()

  function _chatId(data) {
    return data?.chat_id || chatIdFromKey(currentSessionId.value)
  }

  function _isCurrent(chatId) {
    return chatId === chatIdFromKey(currentSessionId.value)
  }

  function _ensureLive(data) {
    const id = _chatId(data)
    let state = _liveCache.get(id)
    if (!state) {
      state = { content: [], agent_name: data?.agent_name || '', toolRunning: false }
      _liveCache.set(id, state)
    } else if (data?.agent_name && !state.agent_name) {
      state.agent_name = data.agent_name
    }
    return state
  }

  function _syncLive(chatId) {
    if (!_isCurrent(chatId)) return
    const state = _liveCache.get(chatId)
    if (state) {
      liveMessage.value = { role: 'assistant', content: state.content, agent_name: state.agent_name }
      toolRunning.value = state.toolRunning
    }
  }

  function _clearLive(chatId) {
    _liveCache.delete(chatId)
    if (_isCurrent(chatId)) {
      liveMessage.value = null
      toolRunning.value = false
    }
  }

  function _lastTextBlock(state) {
    const last = state.content[state.content.length - 1]
    if (last?.type === 'text') return last
    const block = { type: 'text', text: '' }
    state.content.push(block)
    return block
  }

  async function sendMessage(text, media = []) {
    const userMsg = { role: 'user', content: text, media, timestamp: Date.now() }
    messages.value.push(userMsg)
    const chatId = chatIdFromKey(currentSessionId.value)
    _ensureLive({ chat_id: chatId })
    _syncLive(chatId)

    try {
      const res = await api.post('/chat', {
        message: text,
        session_id: currentSessionId.value,
        media,
      })
      return res
    } catch (e) {
      const idx = messages.value.indexOf(userMsg)
      if (idx !== -1) messages.value.splice(idx, 1)
      _clearLive(chatId)
      throw e
    }
  }

  function onUserMessage(data) {
    const chatId = _chatId(data)
    _ensureLive(data)
    if (!_isCurrent(chatId)) return
    messages.value.push({
      role: 'user',
      content: data.content,
      media: data.media,
      channel: data.channel,
      timestamp: Date.now(),
    })
    _syncLive(chatId)
  }

  function onMessage(data) {
    const chatId = _chatId(data)

    // clear live state for this session regardless of which session is active
    _liveCache.delete(chatId)

    if (!_isCurrent(chatId)) return

    // clear reactive refs only for the current session
    liveMessage.value = null
    toolRunning.value = false

    // deduplicate — loadHistory may have already added this message
    if (data.task_id) {
      const exists = messages.value.some(
        (m) => m.role === 'assistant' && m.task_id === data.task_id
      )
      if (exists) return
    }

    // server content_blocks are the authoritative source — always prefer
    // them over client-accumulated streaming chunks
    const content = data.content_blocks || [{ type: 'text', text: data.content || '' }]

    messages.value.push({
      role: 'assistant',
      content,
      task_id: data.task_id,
      agent_name: data.agent_name,
      timestamp: Date.now(),
    })
  }

  function onThinking(data) {
    const chatId = _chatId(data)
    _ensureLive(data)
    _syncLive(chatId)
  }

  function onTranscription(data) {
    const chatId = _chatId(data)
    if (!_isCurrent(chatId)) return
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'user') {
        const msg = messages.value[i]
        msg.content = msg.content
          ? `${msg.content}\n\n${data.content}`
          : data.content
        break
      }
    }
  }

  function onTyping(data) {
    const chatId = _chatId(data)
    const state = _ensureLive(data)
    state.toolRunning = false
    _syncLive(chatId)
  }

  function onStream(data) {
    const chatId = _chatId(data)
    const state = _ensureLive(data)
    const block = _lastTextBlock(state)
    block.text += data.content || ''
    state.toolRunning = false
    _syncLive(chatId)
  }

  function onStreamEnd(data) {
    // content persists in live state — nothing to clear
  }

  function onToolUse(data) {
    const chatId = _chatId(data)
    const state = _ensureLive(data)
    state.content.push({
      type: 'tool_use',
      name: data.tool,
      description: data.description,
    })
    state.toolRunning = true
    _syncLive(chatId)
  }

  async function loadSessions() {
    sessions.value = await api.get('/chat/sessions')
  }

  let _loadToken = 0

  async function loadHistory(sessionKey) {
    currentSessionId.value = sessionKey
    localStorage.setItem('chat_session', sessionKey)

    // cancellation token: if another loadHistory is called while this
    // fetch is in-flight, the stale result is discarded.
    const token = ++_loadToken
    const data = await api.get(`/chat/sessions/${sessionKey}`)
    if (token !== _loadToken) return

    messages.value = (data.messages || []).map((m) => ({
      ...m,
      timestamp: m.timestamp ? new Date(m.timestamp).getTime() : Date.now(),
    }))

    // restore live state: prefer the client-side cache (websocket events
    // that accumulated while viewing another session) over the backend
    // live_state (which only stores tool_uses, not streamed text).
    // if the backend says nothing is in progress, clear any stale cache.
    const chatId = chatIdFromKey(sessionKey)
    const backendLive = data.live_state?.tool_uses?.length > 0

    if (!backendLive) {
      _liveCache.delete(chatId)
      liveMessage.value = null
      toolRunning.value = false
    } else {
      const cached = _liveCache.get(chatId)
      if (cached) {
        liveMessage.value = { role: 'assistant', content: cached.content, agent_name: cached.agent_name }
        toolRunning.value = cached.toolRunning
      } else {
        liveMessage.value = {
          role: 'assistant',
          content: data.live_state.tool_uses.map((tu) => ({
            type: 'tool_use',
            name: tu.name,
            description: tu.description,
          })),
          agent_name: data.live_state?.agent_name || '',
        }
        toolRunning.value = true
      }
    }
  }

  async function switchSession(sessionKey) {
    await loadHistory(sessionKey)
    await loadSessions()
  }

  async function clearSession(sessionKey) {
    await api.del(`/chat/sessions/${sessionKey}`)
    _liveCache.delete(chatIdFromKey(sessionKey))
    if (sessionKey === currentSessionId.value) {
      messages.value = []
      liveMessage.value = null
      toolRunning.value = false
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
    liveMessage.value = null
    toolRunning.value = false
  }

  return {
    messages,
    sessions,
    currentSessionId,
    liveMessage,
    toolRunning,
    sendMessage,
    onUserMessage,
    onMessage,
    onThinking,
    onTyping,
    onStream,
    onStreamEnd,
    onToolUse,
    onTranscription,
    onSessionsUpdated,
    loadSessions,
    loadHistory,
    switchSession,
    clearSession,
    newSession,
  }
})
