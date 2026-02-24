<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DefaultLayout from './layouts/DefaultLayout.vue'

const route = useRoute()
const showLayout = computed(() => route.name !== 'login')
</script>

<template>
  <DefaultLayout v-if="showLayout">
    <router-view />
  </DefaultLayout>
  <router-view v-else />
</template>

<style>
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: Inter, system-ui, -apple-system, sans-serif;
}
</style>
