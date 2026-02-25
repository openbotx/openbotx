<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <Card class="login-card">
      <template #header>
        <div class="login-header">
          <img src="/logo.png" alt="OpenBotX" class="login-logo" />
          <h1>OpenBotX</h1>
        </div>
      </template>
      <template #content>
        <form @submit.prevent="handleLogin" class="login-form">
          <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
          <div class="form-field">
            <label for="username">Username</label>
            <InputText id="username" v-model="username" class="w-full" autofocus />
          </div>
          <div class="form-field">
            <label for="password">Password</label>
            <Password id="password" v-model="password" class="w-full" :feedback="false" toggle-mask input-class="w-full" />
          </div>
          <Button type="submit" label="Login" icon="pi pi-sign-in" :loading="loading" class="w-full" />
        </form>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 1rem;
  background: inherit;
}

.login-card {
  width: 100%;
  max-width: 400px;
}

.login-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 2rem 1rem 1rem;
}

.login-header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
}

.login-logo {
  width: 40px;
  height: 40px;
  object-fit: contain;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-field label {
  font-size: 0.85rem;
  font-weight: 600;
}
</style>
