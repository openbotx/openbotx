<script setup>
import { onMounted } from 'vue'
import Button from 'primevue/button'
import ChatMessages from '../components/chat/ChatMessages.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

onMounted(async () => {
  await chatStore.loadHistory(chatStore.currentSessionId)
  chatStore.loadSessions()
})

async function handleSend(text) {
  await chatStore.sendMessage(text)
}

function handleNewSession() {
  chatStore.newSession()
}
</script>

<template>
  <div class="chat-page">
    <div class="chat-header">
      <h2>Chat</h2>
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
      :streaming="chatStore.streaming"
      :current-tool-use="chatStore.currentToolUse"
    />
    <ChatInput @send="handleSend" />
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.chat-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

@media (max-width: 768px) {
  .chat-header {
    padding: 0.5rem 0.75rem;
  }

  .chat-header h2 {
    font-size: 1rem;
  }
}
</style>
