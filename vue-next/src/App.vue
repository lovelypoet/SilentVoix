<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import Toast from 'primevue/toast'
import {
  PhGauge,
  PhBarbell,
  PhChartLine,
  PhStack,
  PhTable,
  PhSmiley,
  PhSpeakerHigh,
  PhUser,
  PhInfo,
  PhList,
  PhX
} from '@phosphor-icons/vue'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const authStore = useAuthStore()
const isMobileNavOpen = ref(false)
const mobileNavRef = ref(null)
const mobileNavToggleRef = ref(null)

const canAccessExtendedPages = computed(() => ['editor', 'admin'].includes(authStore.user?.role))
const canAccessAdminPages = computed(() => authStore.user?.role === 'admin')

const isFullscreenLayout = computed(() => {
  if (route.meta.layout === 'empty' || route.meta.layout === 'fullscreen') return true
  return route.name === 'training' && route.query.trainingSession === '1'
})

/*
 * Single source of truth for navigation. The desktop sidebar and the mobile
 * drawer both render from this, so the two menus cannot drift apart and role
 * gating is declared once per destination.
 */
const navSections = computed(() => [
  {
    label: 'Overview',
    items: [
      { to: '/', label: 'Dashboard', icon: PhGauge },
      { to: '/gesture-insights', label: 'Gesture Insights', icon: PhChartLine }
    ]
  },
  {
    label: 'Workspace',
    items: [
      { to: '/training', label: 'Training', icon: PhBarbell },
      { to: '/emotion', label: 'Emotion Studio', icon: PhSmiley },
      { to: '/voice', label: 'Voice Studio', icon: PhSpeakerHigh }
    ]
  },
  {
    label: 'Data & Models',
    items: [
      { to: '/model-library', label: 'Model Library', icon: PhStack, visible: canAccessExtendedPages.value },
      { to: '/csv-library', label: 'CSV Library', icon: PhTable, visible: canAccessAdminPages.value }
    ]
  },
  {
    label: 'Account',
    items: [
      { to: '/profile', label: 'Profile', icon: PhUser },
      { to: '/about', label: 'About', icon: PhInfo }
    ]
  }
].map((section) => ({
  ...section,
  items: section.items.filter((item) => item.visible !== false)
})).filter((section) => section.items.length > 0))

// Page title for the mobile header, so small screens say where they are
// instead of just "Menu".
const currentPageTitle = computed(() => {
  const flat = navSections.value.flatMap((section) => section.items)
  const match = flat.find((item) => item.to === route.path)
  if (match) return match.label
  const name = String(route.name || '')
  if (!name) return 'SilentVoix'
  return name.split('-').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
})

watch(
  () => route.fullPath,
  () => {
    isMobileNavOpen.value = false
  }
)

// Keep focus inside the drawer while it is open, and hand focus back to the
// toggle when it closes - otherwise keyboard users are dropped at the top of
// the document.
const focusableInDrawer = () => {
  if (!mobileNavRef.value) return []
  return Array.from(
    mobileNavRef.value.querySelectorAll('a[href], button:not([disabled])')
  )
}

const onKeydown = (event) => {
  if (!isMobileNavOpen.value) return

  if (event.key === 'Escape') {
    isMobileNavOpen.value = false
    mobileNavToggleRef.value?.focus()
    return
  }

  if (event.key !== 'Tab') return

  const focusable = focusableInDrawer()
  if (focusable.length === 0) return

  const first = focusable[0]
  const last = focusable[focusable.length - 1]

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(isMobileNavOpen, async (open) => {
  // Stop the page behind the drawer from scrolling.
  document.body.style.overflow = open ? 'hidden' : ''
  if (!open) return
  await nextTick()
  focusableInDrawer()[0]?.focus()
})

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})

const navLinkClass =
  'nav-link focus-ring flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium text-slate-400 hover:bg-slate-900 hover:text-slate-100 transition-colors'
</script>

<template>
  <div class="min-h-screen text-slate-300 flex app-bg">
    <Toast />

    <!-- Desktop sidebar -->
    <aside
      v-if="!isFullscreenLayout"
      class="hidden lg:flex w-60 p-4 flex-col gap-6 sticky top-0 h-screen shrink-0 border-r border-slate-900"
      aria-label="Main navigation"
    >
      <RouterLink to="/" class="focus-ring flex items-center gap-2.5 px-2 py-1 cursor-pointer">
        <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-600 text-sm font-bold text-white">S</span>
        <span class="text-[15px] font-semibold tracking-tight text-slate-100">SilentVoix</span>
      </RouterLink>

      <nav class="flex flex-col gap-6 overflow-y-auto">
        <div v-for="section in navSections" :key="section.label" class="flex flex-col gap-1">
          <div class="px-3 mb-1 text-[11px] font-medium uppercase tracking-wider text-slate-600">
            {{ section.label }}
          </div>
          <RouterLink
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            :class="navLinkClass"
            active-class="nav-active"
          >
            <component :is="item.icon" size="17" weight="bold" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>
    </aside>

    <!-- Mobile drawer scrim -->
    <div
      v-if="!isFullscreenLayout && isMobileNavOpen"
      class="fixed inset-0 z-40 bg-black/60 lg:hidden"
      @click="isMobileNavOpen = false"
    ></div>

    <!-- Mobile drawer -->
    <aside
      v-if="!isFullscreenLayout"
      id="mobile-navigation"
      ref="mobileNavRef"
      class="fixed inset-y-0 left-0 z-50 w-72 border-r border-slate-900 bg-slate-950 p-5 flex flex-col gap-6 transform transition-transform duration-200 lg:hidden overflow-y-auto"
      :class="isMobileNavOpen ? 'translate-x-0' : '-translate-x-full'"
      :aria-hidden="!isMobileNavOpen"
      :inert="!isMobileNavOpen || undefined"
      aria-label="Main navigation"
    >
      <div class="flex items-center justify-between">
        <RouterLink to="/" class="focus-ring flex items-center gap-2.5 cursor-pointer">
          <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-600 text-sm font-bold text-white">S</span>
          <span class="text-[15px] font-semibold tracking-tight text-slate-100">SilentVoix</span>
        </RouterLink>
        <button
          type="button"
          class="focus-ring p-2 rounded-md border border-slate-800 text-slate-400 hover:text-slate-100 hover:border-slate-700 transition-colors"
          aria-label="Close navigation menu"
          @click="isMobileNavOpen = false"
        >
          <PhX size="18" weight="bold" aria-hidden="true" />
        </button>
      </div>

      <nav class="flex flex-col gap-6">
        <div v-for="section in navSections" :key="section.label" class="flex flex-col gap-1">
          <div class="px-3 mb-1 text-[11px] font-medium uppercase tracking-wider text-slate-600">
            {{ section.label }}
          </div>
          <RouterLink
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            :class="navLinkClass"
            active-class="nav-active"
          >
            <component :is="item.icon" size="17" weight="bold" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>
    </aside>

    <!-- Main Content -->
    <main
      class="flex-1 overflow-auto"
      :class="{ 'p-4 sm:p-6 lg:p-8': !isFullscreenLayout }"
    >
      <div
        v-if="!isFullscreenLayout"
        class="mb-5 flex items-center gap-3 lg:hidden"
      >
        <button
          ref="mobileNavToggleRef"
          type="button"
          class="focus-ring p-2 rounded-md border border-slate-800 text-slate-300 hover:text-slate-100 hover:border-slate-700 transition-colors"
          aria-label="Open navigation menu"
          aria-controls="mobile-navigation"
          :aria-expanded="isMobileNavOpen"
          @click="isMobileNavOpen = true"
        >
          <PhList size="18" weight="bold" aria-hidden="true" />
        </button>
        <h1 class="text-sm font-medium text-slate-200">{{ currentPageTitle }}</h1>
      </div>
      <RouterView />
    </main>
  </div>
</template>

<style>
body {
  @apply bg-slate-950;
}

.nav-link {
  position: relative;
}

.nav-active {
  background: rgb(var(--surface-raised) / 0.6);
  color: rgb(248 250 252);
}

.nav-active svg {
  color: rgb(var(--brand-400));
}
</style>
