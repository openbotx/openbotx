<script setup>
import { ref } from 'vue'
import Button from 'primevue/button'
import Textarea from 'primevue/textarea'

const emit = defineEmits(['send'])
const text = ref('')
const attachments = ref([])
const fileInput = ref(null)
const recording = ref(false)
let mediaRecorder = null
let audioChunks = []

function handleSend() {
  const msg = text.value.trim()
  const hasFiles = attachments.value.length > 0
  if (!msg && !hasFiles) return
  emit('send', { text: msg, files: [...attachments.value] })
  text.value = ''
  attachments.value = []
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

function onFilesSelected(e) {
  const files = Array.from(e.target.files || [])
  attachments.value.push(...files)
  e.target.value = ''
}

function removeAttachment(index) {
  attachments.value.splice(index, 1)
}

function fileIcon(file) {
  if (file.type.startsWith('image/')) return 'pi pi-image'
  if (file.type.startsWith('audio/')) return 'pi pi-volume-up'
  return 'pi pi-file'
}

async function toggleRecording() {
  if (recording.value) {
    mediaRecorder?.stop()
    return
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }

    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      recording.value = false

      if (audioChunks.length) {
        const blob = new Blob(audioChunks, { type: 'audio/webm' })
        const now = new Date()
        const ts = now.toTimeString().slice(0, 8).replace(/:/g, '-')
        const file = new File([blob], `recording-${ts}.webm`, { type: 'audio/webm' })
        attachments.value.push(file)
      }
    }

    mediaRecorder.start()
    recording.value = true
  } catch {
    recording.value = false
  }
}
</script>

<template>
  <div class="chat-input">
    <input
      ref="fileInput"
      type="file"
      accept="image/*,audio/*"
      multiple
      hidden
      @change="onFilesSelected"
    />

    <div v-if="attachments.length" class="attachments">
      <div v-for="(file, i) in attachments" :key="i" class="attachment-chip">
        <i :class="fileIcon(file)"></i>
        <span class="attachment-name">{{ file.name }}</span>
        <button class="remove-btn" @click="removeAttachment(i)">
          <i class="pi pi-times"></i>
        </button>
      </div>
    </div>

    <div class="input-row">
      <Button
        icon="pi pi-paperclip"
        rounded
        text
        severity="secondary"
        @click="openFilePicker"
        title="Attach file"
      />
      <Button
        :icon="recording ? 'pi pi-stop-circle' : 'pi pi-microphone'"
        rounded
        text
        :severity="recording ? 'danger' : 'secondary'"
        @click="toggleRecording"
        :title="recording ? 'Stop recording' : 'Record audio'"
        :class="{ 'recording-pulse': recording }"
      />
      <Textarea
        v-model="text"
        placeholder="Type a message..."
        auto-resize
        :rows="1"
        class="input-field"
        @keydown="handleKeydown"
      />
      <Button
        icon="pi pi-send"
        rounded
        @click="handleSend"
        :disabled="!text.trim() && !attachments.length"
      />
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  flex-direction: column;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
  gap: 0.5rem;
}

.input-row {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
}

.input-field {
  flex: 1;
  max-height: 150px;
}

.attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.attachment-chip {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.5rem;
  border-radius: 1rem;
  background: var(--p-content-hover-background);
  font-size: 0.8rem;
  color: var(--p-text-color);
}

.attachment-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  color: var(--p-text-muted-color);
  cursor: pointer;
  padding: 0;
  font-size: 0.7rem;
}

.remove-btn:hover {
  color: var(--p-text-color);
}

.recording-pulse {
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@media (max-width: 768px) {
  .chat-input {
    padding: 0.5rem 0.75rem;
    padding-bottom: max(0.5rem, env(safe-area-inset-bottom));
  }
}
</style>
