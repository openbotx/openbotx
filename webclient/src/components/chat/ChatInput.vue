<script setup>
import { ref } from 'vue'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'

const emit = defineEmits(['send'])
const text = ref('')

function handleSend() {
  const msg = text.value.trim()
  if (!msg) return
  emit('send', msg)
  text.value = ''
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="chat-input">
    <Textarea
      v-model="text"
      placeholder="Type a message..."
      auto-resize
      :rows="1"
      class="input-field"
      @keydown="handleKeydown"
    />
    <Button icon="pi pi-send" rounded @click="handleSend" :disabled="!text.trim()" />
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 0.5rem;
  padding: 1rem;
  border-top: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
  align-items: flex-end;
}

.input-field {
  flex: 1;
  max-height: 150px;
}

@media (max-width: 768px) {
  .chat-input {
    padding: 0.75rem;
    padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
  }
}
</style>
