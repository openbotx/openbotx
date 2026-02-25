<script setup>
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useChannelsStore } from '../stores/channels'

const toast = useToast()
const channelsStore = useChannelsStore()
const telegramToken = ref('')
const telegramUsers = ref('')

onMounted(async () => {
  await channelsStore.loadChannels()
})

async function saveTelegram() {
  await channelsStore.updateChannel('telegram', {
    token: telegramToken.value,
    allowed_users: telegramUsers.value.split(',').map((s) => s.trim()).filter(Boolean),
  })
  toast.add({ severity: 'success', summary: 'Saved', detail: 'Telegram config updated', life: 2000 })
}

async function toggleTelegram(running) {
  try {
    if (running) {
      await channelsStore.stopChannel('telegram')
      toast.add({ severity: 'success', summary: 'Stopped', detail: 'Telegram channel stopped', life: 2000 })
    } else {
      await channelsStore.startChannel('telegram')
      toast.add({ severity: 'success', summary: 'Started', detail: 'Telegram channel started', life: 2000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to toggle Telegram channel', life: 3000 })
    await channelsStore.loadChannels()
  }
}
</script>

<template>
  <div class="channels-page">
    <div class="page-header">
      <h2>Channels</h2>
    </div>
    <div class="channels-grid">
      <Card>
        <template #title>
          <div class="channel-title">
            <i class="pi pi-globe"></i>
            Web
            <Tag value="running" severity="success" />
          </div>
        </template>
        <template #content>
          <p>Built-in web channel. Always active when the server is running.</p>
        </template>
      </Card>

      <Card>
        <template #title>
          <div class="channel-title">
            <i class="pi pi-send"></i>
            Telegram
            <Tag
              :value="channelsStore.channels?.telegram?.running ? 'running' : 'stopped'"
              :severity="channelsStore.channels?.telegram?.running ? 'success' : 'danger'"
            />
          </div>
        </template>
        <template #content>
          <div class="form-group">
            <label>Bot Token</label>
            <InputText v-model="telegramToken" type="password" placeholder="Enter Telegram bot token" class="w-full" />
          </div>
          <div class="form-group">
            <label>Allowed Users (comma-separated)</label>
            <InputText v-model="telegramUsers" placeholder="user1, user2" class="w-full" />
          </div>
          <div class="button-row">
            <Button label="Save" icon="pi pi-save" size="small" severity="secondary" @click="saveTelegram" />
            <Button
              :label="channelsStore.channels?.telegram?.running ? 'Stop' : 'Start'"
              :icon="channelsStore.channels?.telegram?.running ? 'pi pi-stop' : 'pi pi-play'"
              :severity="channelsStore.channels?.telegram?.running ? 'danger' : 'success'"
              size="small"
              @click="toggleTelegram(channelsStore.channels?.telegram?.running)"
            />
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.channels-page {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.page-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.channels-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.channel-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.button-row {
  display: flex;
  gap: 0.5rem;
}

@media (max-width: 768px) {
  .page-header {
    padding: 0.5rem 0.75rem;
  }

  .page-header h2 {
    font-size: 1rem;
  }

  .channels-grid {
    grid-template-columns: 1fr;
    gap: 0.75rem;
    padding: 0.75rem;
  }
}
</style>
