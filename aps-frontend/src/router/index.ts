import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      // Redirect string đơn giản KHÔNG giữ query — nếu MES nhúng iframe ở path '/'
      // (thay vì '/aps' trực tiếp) kèm ?embed=1&lang=...&parentOrigin=..., redirect
      // sẽ âm thầm xoá mất các param đó trước khi mes-bridge đọc được. Forward
      // nguyên query + hash để không mất context.
      redirect: (to) => ({ path: '/aps', query: to.query, hash: to.hash }),
    },
    {
      path: '/aps',
      name: 'aps',
      component: () => import('@/views/aps/aps-work-plan-view.vue'),
    },
    {
      path: '/masters/work-centers',
      name: 'masters.workCenters',
      component: () => import('@/views/masters/work-center-list-view.vue'),
    },
    {
      path: '/masters/items',
      name: 'masters.items',
      component: () => import('@/views/masters/item-list-view.vue'),
    },
    {
      path: '/masters/bom',
      name: 'masters.bom',
      component: () => import('@/views/masters/bom-view.vue'),
    },
    {
      path: '/masters/inventory',
      name: 'masters.inventory',
      component: () => import('@/views/masters/inventory-view.vue'),
    },
    {
      path: '/mps',
      name: 'mps',
      component: () => import('@/views/mps/mps-list-view.vue'),
    },
  ],
})
