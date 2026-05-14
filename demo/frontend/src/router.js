import { createRouter, createWebHistory } from 'vue-router'
import DemoPage from './DemoPage.vue'
import TestPlayground from './TestPlayground.vue'

const routes = [
  { path: '/', name: 'demo', component: DemoPage },
  { path: '/test', name: 'test', component: TestPlayground },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
