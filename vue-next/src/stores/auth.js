import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
    const user = ref(JSON.parse(localStorage.getItem('user')) || null)
    const token = ref(localStorage.getItem('access_token') || null)
    const isAuthenticated = computed(() => !!token.value)

    const login = async (email, password) => {
        try {
            const res = await api.auth.login(email, password)
            token.value = res.access_token
            localStorage.setItem('access_token', res.access_token)

            // Fetch user details
            const userRes = await api.auth.me()
            user.value = userRes
            localStorage.setItem('user', JSON.stringify(userRes))

            return true
        } catch (error) {
            console.error('Login failed:', error)
            throw error
        }
    }

    const logout = async () => {
        try {
            await api.auth.logout()
        } catch (e) {
            // Ignore errors on logout
        } finally {
            user.value = null
            token.value = null
            localStorage.removeItem('user')
            localStorage.removeItem('access_token')
            router.push('/login')
        }
    }

    return {
        user,
        token,
        isAuthenticated,
        login,
        logout
    }
})
