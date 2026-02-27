<script setup>
import { computed } from 'vue'
import Button from 'primevue/button'
import { chatIdFromKey, channelFromKey, sessionLabel } from '../../stores/chat'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  currentSessionId: { type: String, default: '' },
})

const emit = defineEmits(['select', 'delete', 'new'])

const items = computed(() =>
  props.sessions.map((s) => ({
    key: s.key,
    channel: channelFromKey(s.key),
    chatId: chatIdFromKey(s.key),
    label: sessionLabel(s.key),
    updatedAt: s.updated_at,
    active: s.key === props.currentSessionId,
  }))
)

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="session-list">
    <div class="session-list-header">
      <span class="session-list-title">Sessions</span>
      <Button
        icon="pi pi-plus"
        severity="secondary"
        text
        rounded
        size="small"
        @click="emit('new')"
        title="New session"
      />
    </div>
    <div class="session-list-items">
      <button
        v-for="item in items"
        :key="item.key"
        :class="['session-item', { active: item.active }]"
        @click="emit('select', item.key)"
      >
        <div class="session-item-icon">
          <i :class="item.channel === 'heartbeat' ? 'pi pi-heart' : item.channel === 'telegram' ? 'pi pi-send' : 'pi pi-comments'"></i>
        </div>
        <div class="session-item-info">
          <span class="session-item-label">{{ item.label }}</span>
          <span class="session-item-time">{{ formatTime(item.updatedAt) }}</span>
        </div>
        <Button
          v-if="item.channel === 'web'"
          icon="pi pi-trash"
          severity="danger"
          text
          rounded
          size="small"
          class="session-item-delete"
          @click.stop="emit('delete', item.key)"
          title="Delete session"
        />
      </button>
      <div v-if="items.length === 0" class="session-list-empty">
        <span>No sessions yet</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.session-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  height: 3.25rem;
  box-sizing: border-box;
  border-bottom: 1px solid var(--p-content-border-color);
}

.session-list-title {
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.session-list-items {
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.5rem 0.6rem;
  border: none;
  border-radius: var(--p-content-border-radius);
  background: transparent;
  color: var(--p-text-color);
  cursor: pointer;
  transition: background 0.15s;
  text-align: left;
}

.session-item:hover {
  background: var(--p-content-hover-background);
}

.session-item.active {
  background: color-mix(in srgb, var(--p-primary-color) 12%, var(--p-content-background));
}

.session-item-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--p-content-border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 0.8rem;
}

.session-item.active .session-item-icon {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
}

.session-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.session-item-label {
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-item-time {
  font-size: 0.7rem;
  color: var(--p-text-muted-color);
}

.session-item-delete {
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.session-item:hover .session-item-delete {
  opacity: 1;
}

@media (hover: none) {
  .session-item-delete {
    opacity: 1;
  }
}

.session-list-empty {
  padding: 1.5rem;
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 0.85rem;
}
</style>
