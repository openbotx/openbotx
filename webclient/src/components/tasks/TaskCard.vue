<script setup>
import { computed, ref, onUnmounted, watch } from 'vue'
import Tag from 'primevue/tag'
import { useTasksStore } from '../../stores/tasks'

const props = defineProps({
  task: { type: Object, required: true },
})

const emit = defineEmits(['go-to-session'])

const tasksStore = useTasksStore()

const activeTool = computed(() => tasksStore.activeTools.get(props.task.id))

function handleTitleClick() {
  if (props.task.channel && props.task.chat_id) {
    emit('go-to-session', props.task)
  }
}

const severityMap = {
  TODO: 'info',
  DOING: 'warn',
  DONE: 'success',
  ERROR: 'danger',
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const now = ref(Date.now())
let timer = null

function startTimer() {
  if (!timer) {
    timer = setInterval(() => { now.value = Date.now() }, 1000)
  }
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch(() => props.task.state, (state) => {
  if (state === 'DOING') startTimer()
  else stopTimer()
}, { immediate: true })

onUnmounted(stopTimer)

const elapsed = computed(() => {
  if (!props.task.created_at) return 0
  const start = new Date(props.task.created_at).getTime()
  const end = props.task.state === 'DOING' ? now.value : new Date(props.task.updated_at).getTime()
  return Math.max(0, end - start)
})

function formatDuration(ms) {
  if (ms < 1000) return '0s'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rs = s % 60
  if (m < 60) return `${m}m ${rs}s`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return `${h}h ${rm}m`
}
</script>

<template>
  <div :class="['task-card', task.state === 'ERROR' ? 'task-error' : '']">
    <div class="task-header">
      <span class="task-title" @click="handleTitleClick" title="Open chat session">{{ task.title }}</span>
      <Tag :value="task.state" :severity="severityMap[task.state] || 'secondary'" />
    </div>

    <div v-if="task.description" class="task-desc">
      {{ task.description.substring(0, 160) }}
    </div>

    <div v-if="task.state === 'DOING' && activeTool" class="task-active-tool">
      <div class="tool-header">
        <i class="pi pi-spin pi-spinner"></i>
        <span class="tool-name">{{ activeTool.tool || 'Thinking...' }}</span>
      </div>
      <div v-if="activeTool.description && activeTool.tool" class="tool-desc">
        {{ activeTool.description }}
      </div>
    </div>

    <div v-if="task.error" class="task-error-msg">
      <i class="pi pi-exclamation-triangle"></i>
      {{ task.error.substring(0, 200) }}
    </div>

    <div v-if="task.result && task.state === 'DONE'" class="task-result">
      {{ task.result.substring(0, 120) }}
    </div>

    <div class="task-meta">
      <div class="task-meta-left">
        <span v-if="task.agent_name" class="agent-badge">
          <i class="pi pi-user"></i> {{ task.agent_name }}
        </span>
        <span v-if="task.agent_type === 'subagent'" class="agent-badge">
          <i class="pi pi-sitemap"></i> subagent
        </span>
        <span v-if="task.channel && task.channel !== 'web'" class="channel-badge">
          <i :class="task.channel === 'telegram' ? 'pi pi-send' : task.channel === 'cron' ? 'pi pi-clock' : 'pi pi-hashtag'"></i>
          {{ task.channel }}
        </span>
      </div>
      <div class="task-meta-right">
        <span v-if="elapsed > 0" :class="['task-duration', task.state === 'DOING' ? 'task-duration-live' : '']">
          <i :class="task.state === 'DOING' ? 'pi pi-spin pi-stopwatch' : 'pi pi-stopwatch'"></i>
          {{ formatDuration(elapsed) }}
        </span>
        <span class="task-time">{{ formatTime(task.created_at) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.5rem;
  padding: 0.75rem;
  overflow-wrap: break-word;
}

.task-error {
  border-color: var(--p-red-300);
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.task-title {
  font-weight: 600;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  cursor: pointer;
}

.task-title:hover {
  color: var(--p-primary-color);
}

.task-desc {
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
  margin-bottom: 0.4rem;
  line-height: 1.4;
}

.task-active-tool {
  font-size: 0.78rem;
  margin-bottom: 0.4rem;
  background: color-mix(in srgb, var(--p-primary-color) 8%, transparent);
  border-radius: 0.35rem;
  padding: 0.35rem 0.5rem;
}

.task-active-tool .tool-header {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--p-primary-color);
}

.task-active-tool .tool-name {
  font-weight: 600;
}

.task-active-tool .tool-desc {
  color: var(--p-text-muted-color);
  margin-top: 0.2rem;
  line-height: 1.35;
  word-break: break-word;
}

.task-error-msg {
  font-size: 0.78rem;
  color: var(--p-red-400);
  margin-bottom: 0.4rem;
  line-height: 1.4;
  display: flex;
  align-items: flex-start;
  gap: 0.3rem;
}

.task-error-msg i {
  margin-top: 0.1rem;
  flex-shrink: 0;
}

.task-result {
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
  margin-bottom: 0.4rem;
  line-height: 1.4;
  font-style: italic;
}

.task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  gap: 0.5rem;
}

.task-meta-left {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.task-meta-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.agent-badge,
.channel-badge {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  background: color-mix(in srgb, var(--p-text-color) 8%, transparent);
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
}

.task-duration {
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.task-duration-live {
  color: var(--p-primary-color);
  font-weight: 600;
}
</style>
