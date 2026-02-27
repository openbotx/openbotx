<script setup>
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import { useWebSocketStore } from '../../stores/websocket'
import { useAuthStore } from '../../stores/auth'
import { useDark, toggleDark } from '../../composables/useDark'

const router = useRouter()
const wsStore = useWebSocketStore()
const authStore = useAuthStore()
const darkMode = useDark()

const navItems = [
  { label: 'Chat', icon: 'pi pi-comments', path: '/' },
  { label: 'Tasks', icon: 'pi pi-th-large', path: '/tasks' },
  { label: 'Files', icon: 'pi pi-folder', path: '/files' },
  { label: 'Skills', icon: 'pi pi-bolt', path: '/skills' },
  { label: 'Tools', icon: 'pi pi-wrench', path: '/tools' },
  { label: 'Scheduler', icon: 'pi pi-clock', path: '/scheduler' },
  { label: 'Settings', icon: 'pi pi-cog', path: '/settings' },
]

function navigate(path) {
  router.push(path)
}

function toggleDarkMode() {
  toggleDark()
}

function logout() {
  authStore.logout()
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <img src="/logo.png" alt="OpenBotX" class="logo-icon" />
        <span class="logo-text">OpenBotX</span>
      </div>
      <div class="sidebar-status">
        <span :class="['status-dot', wsStore.connected ? 'online' : 'offline']"></span>
        <span class="status-label">{{ wsStore.connected ? 'Connected' : 'Offline' }}</span>
      </div>
    </div>

    <nav class="sidebar-nav">
      <button
        v-for="item in navItems"
        :key="item.path"
        :class="['nav-item', { active: $route.path === item.path }]"
        @click="navigate(item.path)"
        :title="item.label"
      >
        <i :class="item.icon"></i>
        <span class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <Button
        :icon="darkMode ? 'pi pi-sun' : 'pi pi-moon'"
        severity="secondary"
        text
        rounded
        size="small"
        @click="toggleDarkMode"
      />
      <Button
        icon="pi pi-sign-out"
        severity="secondary"
        text
        rounded
        size="small"
        @click="logout"
        title="Logout"
      />
    </div>
  </aside>

  <nav class="mobile-nav">
    <button
      v-for="item in navItems.slice(0, 5)"
      :key="item.path"
      :class="['mobile-nav-item', { active: $route.path === item.path }]"
      @click="navigate(item.path)"
    >
      <i :class="item.icon"></i>
    </button>
    <button class="mobile-nav-item" @click="navigate('/settings')">
      <i class="pi pi-cog"></i>
    </button>
  </nav>
</template>

<style scoped>
.sidebar {
  width: 240px;
  min-width: 240px;
  background: var(--p-content-background);
  border-right: 1px solid var(--p-content-border-color);
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.sidebar-header {
  padding: 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.logo-icon {
  width: 32px;
  height: 32px;
  object-fit: contain;
}

.logo-text {
  font-size: 1.25rem;
  font-weight: 700;
}

.sidebar-status {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online { background: var(--p-green-500); }
.status-dot.offline { background: var(--p-red-500); }

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: none;
  border-radius: var(--p-content-border-radius);
  background: transparent;
  color: var(--p-text-color);
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.15s;
}

.nav-item:hover {
  background: var(--p-content-hover-background);
}

.nav-item.active {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
}

.nav-item i {
  font-size: 1rem;
  width: 1.25rem;
  text-align: center;
}

.sidebar-footer {
  padding: 0.5rem;
  border-top: 1px solid var(--p-content-border-color);
  display: flex;
  justify-content: center;
  gap: 0.25rem;
}

.mobile-nav {
  display: none;
}

@media (max-width: 768px) {
  .sidebar {
    display: none;
  }

  .mobile-nav {
    display: flex;
    justify-content: space-around;
    background: var(--p-content-background);
    border-top: 1px solid var(--p-content-border-color);
    padding: 0.4rem 0;
    padding-bottom: max(0.4rem, env(safe-area-inset-bottom));
  }

  .mobile-nav-item {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem;
    border: none;
    border-radius: var(--p-content-border-radius);
    background: transparent;
    color: var(--p-text-muted-color);
    font-size: 1.2rem;
    cursor: pointer;
  }

  .mobile-nav-item.active {
    color: var(--p-primary-color);
  }
}
</style>
