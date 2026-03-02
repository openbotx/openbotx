<script setup>
import { ref, watch, nextTick } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  liveMessage: { type: Object, default: null },
  toolRunning: { type: Boolean, default: false },
})

const container = ref(null)

const renderer = new marked.Renderer()
const defaultLinkRenderer = renderer.link.bind(renderer)
renderer.link = function (args) {
  const html = defaultLinkRenderer(args)
  return html.replace('<a ', '<a target="_blank" rel="noopener noreferrer" ')
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked(text, { breaks: true, renderer })
}

function isImage(path) {
  return /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(path)
}

function isAudio(path) {
  return /\.(mp3|wav|ogg|m4a|webm|aac|flac)$/i.test(path)
}

function mediaUrl(path) {
  if (path.startsWith('public/')) return `/${path}`
  return `/api/files/download/${path}`
}

function isLastToolUse(content, index) {
  for (let i = content.length - 1; i >= 0; i--) {
    if (content[i].type === 'tool_use') return i === index
  }
  return false
}

watch(
  [
    () => props.messages.length,
    () => props.liveMessage?.content?.length,
    () => {
      const content = props.liveMessage?.content
      if (!content?.length) return 0
      const last = content[content.length - 1]
      return last?.type === 'text' ? last.text?.length : 0
    },
  ],
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
    <!-- Persisted messages -->
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
        <div v-if="msg.agent_name" class="agent-label">
          <i class="pi pi-user"></i> {{ msg.agent_name }} Agent
        </div>
        <div v-if="msg.media?.length" class="message-media">
          <template v-for="(path, k) in msg.media" :key="k">
            <img v-if="isImage(path)" :src="mediaUrl(path)" class="media-thumb" />
            <audio v-else-if="isAudio(path)" :src="mediaUrl(path)" controls class="media-audio" />
          </template>
        </div>

        <!-- Content blocks array (assistant messages) -->
        <template v-if="Array.isArray(msg.content)">
          <template v-for="(block, k) in msg.content" :key="k">
            <div v-if="block.type === 'text' && block.text" class="message-content" v-html="renderMarkdown(block.text)"></div>
            <div v-else-if="block.type === 'tool_use'" class="tool-use-item">
              <i class="pi pi-cog tool-icon"></i>
              <span class="tool-name">{{ block.name }}</span>
              <span v-if="block.description" class="tool-desc">{{ block.description }}</span>
            </div>
          </template>
        </template>

        <!-- String content (user messages) -->
        <template v-else>
          <div v-if="msg.content" class="message-content" v-html="renderMarkdown(msg.content)"></div>
        </template>
      </div>
    </div>

    <!-- Live message -->
    <div v-if="liveMessage" class="message assistant">
      <div class="message-avatar"><i class="pi pi-sparkles"></i></div>
      <div class="message-body">
        <div v-if="liveMessage.agent_name" class="agent-label">
          <i class="pi pi-user"></i> {{ liveMessage.agent_name }} Agent
        </div>
        <template v-for="(block, k) in liveMessage.content" :key="k">
          <div v-if="block.type === 'text' && block.text" class="message-content" v-html="renderMarkdown(block.text)"></div>
          <div v-else-if="block.type === 'tool_use'" class="tool-use-item">
            <i
              :class="[
                'pi',
                toolRunning && isLastToolUse(liveMessage.content, k)
                  ? 'pi-spin pi-spinner'
                  : 'pi-cog',
                'tool-icon',
              ]"
            ></i>
            <span class="tool-name">{{ block.name }}</span>
            <span v-if="block.description" class="tool-desc">{{ block.description }}</span>
          </div>
        </template>
        <div class="typing-indicator">
          <span></span><span></span><span></span>
          <small class="typing-label">Processing…</small>
        </div>
      </div>
    </div>

    <div v-if="messages.length === 0 && !liveMessage" class="empty-state">
      <i class="pi pi-comments" style="font-size: 3rem; color: var(--p-text-muted-color)"></i>
      <p>Send a message to start a conversation</p>
    </div>
  </div>
</template>

<style scoped>
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  display: flex;
  gap: 0.5rem;
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
  padding: 0.6rem 0.85rem;
  line-height: 1.5;
  overflow-wrap: break-word;
  min-width: 0;
}

.agent-label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--p-primary-color);
  margin-bottom: 0.25rem;
  text-transform: capitalize;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.agent-label i {
  font-size: 0.7rem;
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
  background: var(--p-content-hover-background);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.85rem;
}

.message-content :deep(code) {
  font-family: 'SF Mono', monospace;
  font-size: 0.85em;
}

.message-media {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.media-thumb {
  max-width: 240px;
  max-height: 200px;
  border-radius: 0.5rem;
  object-fit: cover;
  cursor: pointer;
}

.media-audio {
  min-width: 250px;
  max-width: 300px;
  height: 36px;
}

.message-content + .tool-use-item {
  margin-top: 0.5rem;
}

.tool-use-item {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.tool-use-item + .message-content {
  margin-top: 0.5rem;
}

.tool-icon {
  flex-shrink: 0;
  font-size: 0.75rem;
}

.tool-name {
  font-weight: 600;
  color: var(--p-primary-color);
  white-space: nowrap;
  flex-shrink: 0;
}

.tool-desc {
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 0.4rem;
  padding: 0.25rem 0;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--p-primary-color);
  animation: typing 1.4s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

.typing-label {
  margin-left: 0.3rem;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

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

@media (max-width: 768px) {
  .chat-messages {
    padding: 0.75rem;
    gap: 0.75rem;
  }

  .message {
    max-width: 95%;
    gap: 0.5rem;
  }

  .message-avatar {
    width: 28px;
    height: 28px;
    font-size: 0.8rem;
  }

  .message-body {
    padding: 0.5rem 0.75rem;
  }

  .tool-use-item {
    flex-wrap: wrap;
  }

  .tool-desc {
    white-space: normal;
  }

  .media-thumb {
    max-width: 180px;
    max-height: 150px;
  }

  .media-audio {
    max-width: 100%;
  }

  .message-content :deep(pre) {
    font-size: 0.8rem;
    padding: 0.5rem;
  }
}
</style>
