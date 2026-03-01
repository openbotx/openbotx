import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'login', component: () => import('../pages/LoginPage.vue'), meta: { public: true } },
  { path: '/', name: 'chat', component: () => import('../pages/ChatPage.vue') },
  { path: '/tasks', name: 'tasks', component: () => import('../pages/TaskBoard.vue') },
  { path: '/files', name: 'files', component: () => import('../pages/FilesPage.vue') },
  { path: '/skills', name: 'skills', component: () => import('../pages/SkillsPage.vue') },
  { path: '/tools', name: 'tools', component: () => import('../pages/ToolsPage.vue') },
  { path: '/marketplace', name: 'marketplace', component: () => import('../pages/MarketplacePage.vue') },
  { path: '/scheduler', name: 'scheduler', component: () => import('../pages/SchedulerPage.vue') },
  { path: '/settings', name: 'settings', component: () => import('../pages/SettingsPage.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory('/app/'),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const token = localStorage.getItem('openbotx_token')
  if (!token) return { name: 'login' }
  return true
})

export default router
