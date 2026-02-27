import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'

export const useAgentsStore = defineStore('agents', () => {
  const api = useApi()
  const agents = ref([])

  async function loadAgents() {
    agents.value = await api.get('/agents')
  }

  return { agents, loadAgents }
})
