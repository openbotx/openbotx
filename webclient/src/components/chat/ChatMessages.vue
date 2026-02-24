<script setup>
import { ref, watch, nextTick } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  streaming: { type: Boolean, default: false },
  currentToolUse: { type: Object, default: null },
})

const container = ref(null)

function renderMarkdown(text) {
  if (!text) return ''
  return marked(text, { breaks: true })
}

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (container.value) {
      container.value.scrollTop = container.value.scrollHeight
    }
  }
)
</script>

<template>
  <div ref="container" class="chat-messages">
    <div
      v-for="(msg, i) in messages"
      :key="i"
      :class="['message', msg.role]"
    >
      <div class="message-avatar">
        <i v-if="msg.role === 'user'" class="pi pi-user"></i>
        <i v-else class="pi pi-sparkles"></i>
      </div>
      <div class="message-body">
        <div v-if="msg.content" class="message-content" v-html="renderMarkdown(msg.content)"></div>
        <div v-if="msg.tool_uses" class="tool-uses">
          <div v-for="(tu, j) in msg.tool_uses" :key="j" class="tool-use-item">
            <i class="pi pi-cog"></i>
            <span class="tool-name">{{ tu.tool }}</span>
            <span v-if="tu.description" class="tool-desc">{{ tu.description }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="streaming && currentToolUse" class="message assistant">
      <div class="message-avatar"><i class="pi pi-sparkles"></i></div>
      <div class="tool-indicator">
        <i class="pi pi-spin pi-spinner"></i>
        <span>{{ currentToolUse.description || currentToolUse.tool }}</span>
      </div>
    </div>

    <div v-if="streaming && !currentToolUse" class="message assistant">
      <div class="message-avatar"><i class="pi pi-sparkles"></i></div>
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>

    <div v-if="messages.length === 0 && !streaming" class="empty-state">
      <i class="pi pi-comments" style="font-size: 3rem; color: var(--p-text-muted-color)"></i>
      <p>Send a message to start a conversation</p>
    </div>
  </div>
</template>

<style scoped>
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message {
  display: flex;
  gap: 0.75rem;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--p-content-border-color);
  color: var(--p-text-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
}

.message-body {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.75rem;
  padding: 0.75rem 1rem;
  line-height: 1.5;
}

.message.user .message-body {
  background: color-mix(in srgb, var(--p-primary-color) 12%, var(--p-content-background));
  border-color: color-mix(in srgb, var(--p-primary-color) 25%, var(--p-content-background));
}

.message-content :deep(p) {
  margin: 0 0 0.5rem 0;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-content :deep(pre) {
  background: var(--p-surface-100);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.85rem;
}

.message-content :deep(code) {
  font-family: 'SF Mono', monospace;
  font-size: 0.85em;
}

.tool-uses {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.tool-use-item {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.tool-name {
  font-weight: 600;
  color: var(--p-primary-color);
}

.tool-desc {
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--p-primary-color);
  padding: 0.5rem 0;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0.75rem 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--p-text-muted-color);
  animation: typing 1.4s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  color: var(--p-text-muted-color);
}
</style>
