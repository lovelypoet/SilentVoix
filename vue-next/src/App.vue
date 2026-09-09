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

const frameExcludedRoutes = new Set(['profile', 'training'])
const canAccessExtendedPages = computed(() => ['editor', 'admin'].includes(authStore.user?.role))
const canAccessAdminPages = computed(() => authStore.user?.role === 'admin')

const isFullscreenLayout = computed(() => {
  if (route.meta.layout === 'empty' || route.meta.layout === 'fullscreen') return true
  return route.name === 'training' && route.query.trainingSession === '1'
})
const useContentFrame = computed(() => !isFullscreenLayout.value && !frameExcludedRoutes.has(String(route.name || '')))

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
  'nav-link focus-ring flex items-center gap-3 p-3 rounded font-semibold text-slate-300 hover:bg-slate-900 hover:text-brand-300 transition-colors'
</script>

<template>
  <!-- No background colour here: .app-bg paints its gradient layers at z-index -1,
       and body already supplies the slate-950 base. -->
  <div class="min-h-screen text-slate-200 flex app-bg">
    <Toast />
    <svg
      aria-hidden="true"
      width="0"
      height="0"
      class="absolute pointer-events-none"
      focusable="false"
    >
      <filter id="frosted" x="-20%" y="-20%" width="140%" height="140%" color-interpolation-filters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="0.015 0.04" numOctaves="1" seed="7" result="noise" />
        <feDisplacementMap in="SourceGraphic" in2="noise" scale="7" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </svg>

    <!-- Desktop sidebar -->
    <aside
      v-if="!isFullscreenLayout"
      class="hidden lg:flex w-56 p-5 flex-col sticky top-0 h-screen shrink-0"
      aria-label="Main navigation"
    >
      <RouterLink to="/" class="focus-ring text-2xl font-bold text-brand-300 mb-8 cursor-pointer">
        SilentVoix
      </RouterLink>

      <nav class="flex flex-col gap-5 overflow-y-auto">
        <div v-for="section in navSections" :key="section.label" class="flex flex-col gap-1">
          <div class="px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            {{ section.label }}
          </div>
          <RouterLink
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            :class="navLinkClass"
            active-class="nav-active"
          >
            <component :is="item.icon" size="18" weight="bold" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>

      <div class="mt-auto"></div>
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
      class="fixed inset-y-0 left-0 z-50 w-72 border-r border-slate-800 bg-slate-950 p-6 flex flex-col transform transition-transform duration-200 lg:hidden overflow-y-auto"
      :class="isMobileNavOpen ? 'translate-x-0' : '-translate-x-full'"
      :aria-hidden="!isMobileNavOpen"
      :inert="!isMobileNavOpen || undefined"
      aria-label="Main navigation"
    >
      <div class="flex items-center justify-between mb-8">
        <RouterLink to="/" class="focus-ring text-2xl font-bold text-brand-300 cursor-pointer">
          SilentVoix
        </RouterLink>
        <button
          type="button"
          class="focus-ring p-2 rounded border border-slate-700 text-slate-300 hover:text-brand-300 transition-colors"
          aria-label="Close navigation menu"
          @click="isMobileNavOpen = false"
        >
          <PhX size="18" weight="bold" aria-hidden="true" />
        </button>
      </div>

      <nav class="flex flex-col gap-5">
        <div v-for="section in navSections" :key="section.label" class="flex flex-col gap-1">
          <div class="px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            {{ section.label }}
          </div>
          <RouterLink
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            :class="navLinkClass"
            active-class="nav-active"
          >
            <component :is="item.icon" size="18" weight="bold" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>

      <div class="mt-auto"></div>
    </aside>

    <!-- Main Content -->
    <main
      class="flex-1 overflow-auto"
      :class="{
        'p-4 sm:p-6 lg:py-8 lg:pr-8 lg:pl-0 lg:border-l lg:border-slate-800': !isFullscreenLayout
      }"
    >
      <div
        v-if="!isFullscreenLayout"
        class="mb-4 flex items-center gap-3 lg:hidden"
      >
        <button
          ref="mobileNavToggleRef"
          type="button"
          class="focus-ring p-2 rounded border border-slate-700 text-slate-200 hover:text-brand-300 transition-colors"
          aria-label="Open navigation menu"
          aria-controls="mobile-navigation"
          :aria-expanded="isMobileNavOpen"
          @click="isMobileNavOpen = true"
        >
          <PhList size="18" weight="bold" aria-hidden="true" />
        </button>
        <h1 class="text-sm font-semibold text-slate-200">{{ currentPageTitle }}</h1>
      </div>
      <div
        v-if="useContentFrame"
        class="content-frame"
      >
        <RouterView />
      </div>
      <RouterView v-else />
    </main>
  </div>
</template>

<style>
body {
  @apply bg-slate-950;
}

.nav-link {
  position: relative;
  z-index: 0;
}

.nav-active {
  color: rgb(var(--brand-300));
  animation: nav-bounce 420ms ease;
}

.nav-active::before {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgb(var(--brand-500) / 0.18), rgba(15, 23, 42, 0.25));
  border: 1px solid rgb(var(--brand-400) / 0.25);
  z-index: -1;
}

@keyframes nav-bounce {
  0% { transform: translateY(0); }
  35% { transform: translateY(-4px); }
  100% { transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .nav-active {
    animation: none;
  }
}

.content-frame {
  width: 100%;
  margin-top: 0.75rem;
  border-radius: 18px;
  border: 1px solid rgb(var(--brand-400) / 0.25);
  background:
    linear-gradient(180deg, rgb(var(--brand-400) / 0.08), rgba(15, 23, 42, 0.0) 18%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.62), rgba(2, 6, 23, 0.85));
  box-shadow: 0 20px 45px rgba(2, 6, 23, 0.45);
  padding: 1rem;
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
}

@supports (backdrop-filter: url(#frosted)) or (-webkit-backdrop-filter: url(#frosted)) {
  .content-frame {
    backdrop-filter: url(#frosted) blur(12px) saturate(130%);
    -webkit-backdrop-filter: url(#frosted) blur(12px) saturate(130%);
  }
}

@media (min-width: 640px) {
  .content-frame {
    margin-top: 1rem;
    padding: 1.25rem;
  }
}

@media (min-width: 1024px) {
  .content-frame {
    margin-top: 1.5rem;
    margin-left: 1.5rem;
    width: calc(100% - 1.5rem);
    max-width: none;
    padding: 1.5rem;
  }
}
</style>
