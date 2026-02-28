import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'

export const useConfigStore = defineStore('config', () => {
  const api = useApi()
  const config = ref(null)

  async function loadConfig() {
    config.value = await api.get('/config')
  }

  async function saveSection(section, data) {
    await api.put(`/config/${section}`, { data })
    await loadConfig()
  }

  return { config, loadConfig, saveSection }
})
