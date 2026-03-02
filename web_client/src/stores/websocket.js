import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useChannelsStore } from './channels'
import { useChatStore } from './chat'
import { useTasksStore } from './tasks'
import { useAuthStore } from './auth'

export const useWebSocketStore = defineStore('websocket', () => {
  const connected = ref(false)
  let ws = null
  let reconnectTimer = null
  let reconnectDelay = 1000

  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return

    const auth = useAuthStore()
    if (!auth.token) return

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/ws?token=${auth.token}`)

    ws.onopen = () => {
      connected.value = true
      reconnectDelay = 1000
      syncAfterReconnect()
    }

    ws.onclose = (event) => {
      connected.value = false
      if (event.code === 4001) {
        auth.logout()
        return
      }
      scheduleReconnect()
    }

    ws.onerror = () => {
      connected.value = false
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        dispatch(msg)
      } catch (e) {
        console.error('ws parse error:', e)
      }
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      reconnectDelay = Math.min(reconnectDelay * 2, 30000)
      connect()
    }, reconnectDelay)
  }

  function dispatch(msg) {
    const channels = useChannelsStore()
    const chat = useChatStore()
    const tasks = useTasksStore()

    switch (msg.type) {
      case 'channel:status':
        channels.onChannelStatus(msg.data)
        break
      case 'chat:message':
        chat.onMessage(msg.data)
        break
      case 'chat:thinking':
        chat.onThinking(msg.data)
        tasks.onThinking(msg.data)
        break
      case 'chat:typing':
        chat.onTyping(msg.data)
        break
      case 'chat:stream':
        chat.onStream(msg.data)
        break
      case 'chat:stream_end':
        chat.onStreamEnd(msg.data)
        break
      case 'chat:tool_use':
        chat.onToolUse(msg.data)
        tasks.onToolUse(msg.data)
        break
      case 'chat:user_message':
        chat.onUserMessage(msg.data)
        break
      case 'chat:transcription':
        chat.onTranscription(msg.data)
        break
      case 'sessions:updated':
        chat.onSessionsUpdated()
        break
      case 'task:created':
        tasks.onTaskCreated(msg.data)
        break
      case 'task:updated':
        tasks.onTaskUpdated(msg.data)
        break
    }
  }

  function send(type, data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, data }))
    }
  }

  function syncAfterReconnect() {
    const tasks = useTasksStore()
    const chat = useChatStore()
    tasks.loadTasks()
    chat.loadHistory(chat.currentSessionId)
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
  }

  return { connected, connect, disconnect, send }
})
