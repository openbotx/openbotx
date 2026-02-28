<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DefaultLayout from './layouts/DefaultLayout.vue'

const route = useRoute()
const router = useRouter()
const ready = ref(false)

router.isReady().then(() => {
  ready.value = true
})

const showLayout = computed(() => route.name !== 'login')
</script>

<template>
  <template v-if="ready">
    <DefaultLayout v-if="showLayout">
      <router-view />
    </DefaultLayout>
    <router-view v-else />
  </template>
</template>

<style>
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: Inter, system-ui, -apple-system, sans-serif;
}
</style>
