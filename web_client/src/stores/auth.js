import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('openbotx_token') || '')
  const username = ref(localStorage.getItem('openbotx_username') || '')
  const isAuthenticated = computed(() => !!token.value)

  async function login(user, password) {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password }),
    })

    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.error || 'Login failed')
    }

    const data = await res.json()
    token.value = data.token
    username.value = data.username
    localStorage.setItem('openbotx_token', data.token)
    localStorage.setItem('openbotx_username', data.username)
  }

  function logout() {
    token.value = ''
    username.value = ''
    localStorage.removeItem('openbotx_token')
    localStorage.removeItem('openbotx_username')
    router.push('/login')
  }

  return { token, username, isAuthenticated, login, logout }
})
