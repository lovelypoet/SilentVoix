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
            path: '/fusion',
            name: 'fusion',
            component: () => import('../views/FusionWorkspace.vue'),
            meta: { requiresAuth: true, layout: 'fullscreen', allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/realtime-ai-playground',
            name: 'realtime-ai-playground',
            component: () => import('../views/RealtimeAIPlayground.vue'),
            meta: { requiresAuth: true, layout: 'fullscreen', allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/fusion/early-module',
            name: 'fusion-early-module',
            component: () => import('../views/CaptureSession.vue'),
            meta: { requiresAuth: true, layout: 'fullscreen', allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/fusion/early-cropper',
            name: 'fusion-early-cropper',
            component: () => import('../views/EarlyFusionCropper.vue'),
            meta: { requiresAuth: true, layout: 'fullscreen', allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/dataset-aligner',
            name: 'dataset-aligner',
            component: () => import('../views/DatasetAligner.vue'),
            meta: { requiresAuth: true, layout: 'fullscreen', allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/fusion/late-module',
            redirect: '/dataset-aligner'
        },
        {
            path: '/late-fusion-training',
            redirect: '/dataset-aligner'
        },
        {
            path: '/early-fusion-training',
            redirect: '/fusion/early-module'
        },
        {
            path: '/fusion-training',
            redirect: '/fusion/early-module'
        },
        {
            path: '/capture',
            redirect: '/fusion/early-module'
        },
        {
            path: '/voice',
            name: 'voice',
            component: () => import('../views/VoiceStudio.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/gesture-insights',
            name: 'gesture-insights',
            component: () => import('../views/GestureInsights.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/library',
            redirect: '/gesture-insights'
        },
        {
            path: '/model-library',
            name: 'model-library',
            component: () => import('../views/ModelLibrary.vue'),
            meta: { requiresAuth: true, allowedRoles: ['editor', 'admin'] }
        },
        {
            path: '/profile',
            name: 'profile',
            component: () => import('../views/Profile.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/about',
            name: 'about',
            component: () => import('../views/About.vue'),
            meta: { requiresAuth: true }
        },
        {
            path: '/csv-library',
            name: 'csv-library',
            component: () => import('../views/CsvLibrary.vue'),
            meta: { requiresAuth: true, allowedRoles: ['admin'] }
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
