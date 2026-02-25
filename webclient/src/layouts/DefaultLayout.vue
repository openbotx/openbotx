<script setup>
import { onMounted } from 'vue'
import Toast from 'primevue/toast'
import AppSidebar from '../components/common/AppSidebar.vue'
import { useWebSocketStore } from '../stores/websocket'

const wsStore = useWebSocketStore()

onMounted(() => {
  wsStore.connect()
})
</script>

<template>
  <Toast position="bottom-right" :breakpoints="{ '768px': { width: 'calc(100% - 1.5rem)', right: '0.75rem', left: '0.75rem', bottom: '0.75rem' } }" />
  <div class="layout">
    <AppSidebar />
    <main class="layout-main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100dvh;
  overflow: hidden;
}

.layout-main {
  flex: 1;
  overflow: auto;
  min-width: 0;
  background: inherit;
}

@media (max-width: 768px) {
  .layout {
    flex-direction: column-reverse;
  }

  .layout-main {
    flex: 1;
    height: 0;
    overflow: auto;
  }
}
</style>
