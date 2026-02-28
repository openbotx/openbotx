import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'

export const useChannelsStore = defineStore('channels', () => {
  const api = useApi()
  const channels = ref({})

  async function loadChannels() {
    channels.value = await api.get('/channels')
  }

  async function updateChannel(name, config) {
    await api.put(`/channels/${name}`, { config })
    await loadChannels()
  }

  async function startChannel(name) {
    await api.post(`/channels/${name}/start`)
    await loadChannels()
  }

  async function stopChannel(name) {
    await api.post(`/channels/${name}/stop`)
    await loadChannels()
  }

  function onChannelStatus(data) {
    if (channels.value[data.name]) {
      channels.value[data.name].running = data.running
    } else {
      channels.value[data.name] = { running: data.running, type: data.name }
    }
  }

  return { channels, loadChannels, updateChannel, startChannel, stopChannel, onChannelStatus }
})
