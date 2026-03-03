import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/login',
            name: 'login',
            component: () => import('../views/Login.vue'),
            meta: { layout: 'empty' }
        },
        {
            path: '/register',
            name: 'register',
            component: () => import('../views/Register.vue'),
            meta: { layout: 'empty' }
        },
        {
            path: '/',
            name: 'dashboard',
            component: () => import('../views/Dashboard.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/training',
            name: 'training',
            component: () => import('../views/Training.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/sensor-training',
            name: 'sensor-training',
            component: () => import('../views/SensorTraining.vue'),
            meta: { requiresAuth: true, layout: 'fullscreen', allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/fusion-training',
            name: 'fusion-training',
            component: () => import('../views/CaptureSession.vue'),
            meta: { requiresAuth: true, layout: 'fullscreen', allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/capture',
            redirect: '/fusion-training'
        },
        {
            path: '/voice',
            name: 'voice',
            component: () => import('../views/VoiceStudio.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/library',
            name: 'library',
            component: () => import('../views/Library.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/profile',
            name: 'profile',
            component: () => import('../views/Profile.vue'),
            meta: { requiresAuth: true }
        }
    ]
})

router.beforeEach((to, from, next) => {
    const authStore = useAuthStore()

    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        next('/login')
    } else if (to.meta.allowedRoles && !to.meta.allowedRoles.includes(authStore.user?.role)) {
        next('/')
    } else if ((to.name === 'login' || to.name === 'register') && authStore.isAuthenticated) {
        next('/')
    } else {
        next()
    }
})

export default router
