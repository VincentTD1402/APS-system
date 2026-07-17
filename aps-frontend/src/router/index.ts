import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/aps',
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
