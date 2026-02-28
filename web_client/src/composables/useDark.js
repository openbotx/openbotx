import { ref } from 'vue'

function getInitialDark() {
  const saved = localStorage.getItem('dark-mode')
  if (saved !== null) return saved === 'true'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

const isDark = ref(getInitialDark())
document.documentElement.classList.toggle('dark-mode', isDark.value)

export function useDark() {
  return isDark
}

export function toggleDark() {
  isDark.value = !isDark.value
  localStorage.setItem('dark-mode', isDark.value)
  document.documentElement.classList.toggle('dark-mode', isDark.value)
}
