<script setup>
import { onMounted, ref, computed } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ChatMessages from '../components/chat/ChatMessages.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import SessionList from '../components/chat/SessionList.vue'
import { useChatStore, sessionLabel } from '../stores/chat'
import { useApi } from '../composables/useApi'

const api = useApi()
const chatStore = useChatStore()
const isMobile = window.innerWidth <= 768
const showSessions = ref(!isMobile)
const showDeleteConfirm = ref(false)
const deleteTargetKey = ref('')

const currentLabel = computed(() => {
  const match = chatStore.sessions.find(
    (s) => s.key === chatStore.currentSessionId
  )
  return match ? sessionLabel(match.key) : 'Chat'
})

const deleteTargetLabel = computed(() => sessionLabel(deleteTargetKey.value))

onMounted(async () => {
  await chatStore.loadHistory(chatStore.currentSessionId)
  chatStore.loadSessions()
})

async function handleSend({ text, files }) {
  let media = []
  if (files?.length) {
    const res = await api.upload('/chat/upload', files)
    media = res.paths || []
  }
  await chatStore.sendMessage(text, media)
}

function handleNewSession() {
  chatStore.newSession()
}

async function handleSelectSession(key) {
  await chatStore.switchSession(key)
  if (isMobile) showSessions.value = false
}

function handleDeleteSession(sessionKey) {
  deleteTargetKey.value = sessionKey
  showDeleteConfirm.value = true
}

async function confirmDeleteSession() {
  showDeleteConfirm.value = false
  await chatStore.clearSession(deleteTargetKey.value)
}

function toggleSessions() {
  showSessions.value = !showSessions.value
}
</script>

<template>
  <div class="chat-page">
    <Teleport to="body">
      <div v-if="showSessions" class="mobile-overlay" @click="showSessions = false"></div>
    </Teleport>
    <SessionList
      v-if="showSessions"
      :sessions="chatStore.sessions"
      :current-session-id="chatStore.currentSessionId"
      class="chat-sessions"
      @select="handleSelectSession"
      @delete="handleDeleteSession"
      @new="handleNewSession"
    />
    <div class="chat-main">
      <div class="chat-header">
        <div class="chat-header-left">
          <Button
            :icon="showSessions ? 'pi pi-chevron-left' : 'pi pi-list'"
            severity="secondary"
            text
            rounded
            size="small"
            @click="toggleSessions"
            title="Toggle sessions"
          />
          <h2>{{ currentLabel }}</h2>
        </div>
        <Button
          icon="pi pi-plus"
          label="New"
          severity="secondary"
          text
          size="small"
          @click="handleNewSession"
        />
      </div>
      <ChatMessages
        :messages="chatStore.messages"
        :live-message="chatStore.liveMessage"
        :tool-running="chatStore.toolRunning"
      />
      <ChatInput @send="handleSend" />
    </div>

    <Dialog v-model:visible="showDeleteConfirm" header="Delete Session" :modal="true" :style="{ width: '24rem' }" :breakpoints="{ '768px': '90vw' }">
      <p>Delete session <strong>{{ deleteTargetLabel }}</strong>?</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showDeleteConfirm = false" />
        <Button label="Delete" icon="pi pi-trash" severity="danger" size="small" @click="confirmDeleteSession" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  position: relative;
}

.chat-sessions {
  width: 260px;
  min-width: 260px;
  flex-shrink: 0;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  height: 2.75rem;
  box-sizing: border-box;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.mobile-overlay {
  display: none;
}

@media (max-width: 768px) {
  .chat-sessions {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 100;
    width: 280px;
    min-width: 280px;
    box-shadow: 4px 0 16px rgba(0, 0, 0, 0.15);
  }

  .mobile-overlay {
    display: block;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 99;
    background: rgba(0, 0, 0, 0.3);
  }

  .chat-header h2 {
    font-size: 1rem;
  }
}
</style>
