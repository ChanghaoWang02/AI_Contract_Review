import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/rules',
      name: 'rules',
      component: () => import('@/views/RulesView.vue'),
    },
    {
      path: '/draft',
      name: 'draft',
      component: () => import('@/views/DraftView.vue'),
    },
  ],
})

export default router
