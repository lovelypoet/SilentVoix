<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
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
  PhX,
  PhSun,
  PhMoon
} from '@phosphor-icons/vue'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const isMobileNavOpen = ref(false)
const mobileNavRef = ref(null)
const mobileNavToggleRef = ref(null)

const canAccessExtendedPages = computed(() => ['editor', 'admin'].includes(authStore.user?.role))
const canAccessAdminPages = computed(() => authStore.user?.role === 'admin')

// Initials for the account chip at the foot of the sidebar.
const userInitials = computed(() => {
  const source = authStore.user?.display_name || authStore.user?.email || ''
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  return (parts[0]?.[0] || 'S').toUpperCase() + (parts[1]?.[0] || '').toUpperCase()
})
const userLabel = computed(() => authStore.user?.display_name || authStore.user?.email || 'Signed in')

/*
 * Thin progress bar while a lazily-loaded route chunk is fetched. Delayed so
 * instant (cached) navigations never flash it.
 */
const isNavigating = ref(false)
let navTimer = null
const removeBefore = router.beforeEach(() => {
  clearTimeout(navTimer)
  navTimer = setTimeout(() => { isNavigating.value = true }, 90)
})
const stopProgress = () => {
  clearTimeout(navTimer)
  isNavigating.value = false
}
const removeAfter = router.afterEach(stopProgress)
const removeError = router.onError(stopProgress)

/*
 * Tool pages (layout: 'fullscreen', plus an active Training session) hide
 * the sidebar but still sit on the aurora backdrop with padding and the
 * staggered entrance. The auth/marketing screens bring their own
 * backgrounds, and `bleed` views manage their own full-viewport frame.
 */
const isStagedLayout = computed(() => !['empty', 'marketing'].includes(route.meta.layout) && !route.meta.bleed)

const isFullscreenLayout = computed(() => {
  if (['empty', 'fullscreen', 'marketing'].includes(route.meta.layout)) return true
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
      { to: '/dashboard', label: 'Dashboard', icon: PhGauge },
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
  removeBefore()
  removeAfter()
  removeError()
  clearTimeout(navTimer)
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})

const navLinkClass =
  'nav-link focus-ring flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-100'
</script>

<template>
  <div class="min-h-screen text-slate-300 flex app-bg">
    <div v-if="isStagedLayout" class="aurora" aria-hidden="true">
      <div class="aurora-blob aurora-blob-a"></div>
      <div class="aurora-blob aurora-blob-b"></div>
      <div class="aurora-blob aurora-blob-c"></div>
      <div class="aurora-grid"></div>
    </div>
    <Transition name="route-progress">
      <div v-if="isNavigating" class="route-progress" aria-hidden="true"></div>
    </Transition>
    <Toast />
    <a href="#main-content" class="skip-link focus-ring">Skip to main content</a>

    <!-- Desktop sidebar -->
    <aside
      v-if="!isFullscreenLayout"
      class="shell-sidebar hidden lg:flex w-64 p-4 flex-col gap-6 sticky top-0 h-screen shrink-0 z-10"
      aria-label="Main navigation"
    >
      <RouterLink to="/dashboard" class="focus-ring brand-mark px-2 py-1 cursor-pointer">
        <span class="brand-orbit"><span></span></span>
        <span class="text-[15px] font-medium tracking-tight text-slate-100">Silent<span class="text-brand-400">Voix</span></span>
      </RouterLink>

      <nav class="flex flex-col gap-6 overflow-y-auto">
        <div v-for="section in navSections" :key="section.label" class="flex flex-col gap-1">
          <div class="px-3 mb-1 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            {{ section.label }}
          </div>
          <RouterLink
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            :class="navLinkClass"
            active-class="nav-active"
          >
            <span class="nav-icon grid place-items-center">
              <component :is="item.icon" size="17" weight="bold" aria-hidden="true" />
            </span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>

      <div class="shell-footer mt-auto flex flex-col gap-2">
        <button
          type="button"
          class="focus-ring nav-link theme-toggle flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-100"
          @click="themeStore.toggleTheme()"
        >
          <span class="theme-toggle-icon grid place-items-center" :class="{ 'is-light': themeStore.theme === 'light' }">
            <PhSun v-if="themeStore.theme === 'dark'" size="17" weight="bold" aria-hidden="true" />
            <PhMoon v-else size="17" weight="bold" aria-hidden="true" />
          </span>
          <span>{{ themeStore.theme === 'dark' ? 'Light mode' : 'Dark mode' }}</span>
        </button>
        <RouterLink to="/profile" class="focus-ring account-chip flex items-center gap-3 rounded-xl p-2 cursor-pointer">
          <span class="account-avatar grid h-9 w-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-white" aria-hidden="true">{{ userInitials }}</span>
          <span class="min-w-0">
            <span class="block truncate text-sm font-medium text-slate-200">{{ userLabel }}</span>
            <span class="block text-[11px] uppercase tracking-wider text-slate-500">{{ authStore.user?.role || 'member' }}</span>
          </span>
        </RouterLink>
      </div>
    </aside>

    <!-- Mobile drawer scrim -->
    <Transition name="scrim">
      <div
        v-if="!isFullscreenLayout && isMobileNavOpen"
        class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
        @click="isMobileNavOpen = false"
      ></div>
    </Transition>

    <!-- Mobile drawer -->
    <aside
      v-if="!isFullscreenLayout"
      id="mobile-navigation"
      ref="mobileNavRef"
      class="shell-drawer fixed inset-y-0 left-0 z-50 w-72 p-5 flex flex-col gap-6 transform transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] lg:hidden overflow-y-auto"
      :class="isMobileNavOpen ? 'translate-x-0' : '-translate-x-full'"
      :aria-hidden="!isMobileNavOpen"
      :inert="!isMobileNavOpen || undefined"
      aria-label="Main navigation"
    >
      <div class="flex items-center justify-between">
        <RouterLink to="/dashboard" class="focus-ring brand-mark cursor-pointer">
          <span class="brand-orbit"><span></span></span>
          <span class="text-[15px] font-medium tracking-tight text-slate-100">Silent<span class="text-brand-400">Voix</span></span>
        </RouterLink>
        <button
          type="button"
          class="focus-ring icon-btn p-2 rounded-md text-slate-400 hover:text-slate-100 transition-colors"
          aria-label="Close navigation menu"
          @click="isMobileNavOpen = false"
        >
          <PhX size="18" weight="bold" aria-hidden="true" />
        </button>
      </div>

      <nav class="flex flex-col gap-6">
        <div v-for="section in navSections" :key="section.label" class="flex flex-col gap-1">
          <div class="px-3 mb-1 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            {{ section.label }}
          </div>
          <RouterLink
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            :class="navLinkClass"
            active-class="nav-active"
          >
            <span class="nav-icon grid place-items-center">
              <component :is="item.icon" size="17" weight="bold" aria-hidden="true" />
            </span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>

      <div class="shell-footer mt-auto flex flex-col gap-2">
        <button
          type="button"
          class="focus-ring nav-link theme-toggle flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-100"
          @click="themeStore.toggleTheme()"
        >
          <span class="theme-toggle-icon grid place-items-center" :class="{ 'is-light': themeStore.theme === 'light' }">
            <PhSun v-if="themeStore.theme === 'dark'" size="17" weight="bold" aria-hidden="true" />
            <PhMoon v-else size="17" weight="bold" aria-hidden="true" />
          </span>
          <span>{{ themeStore.theme === 'dark' ? 'Light mode' : 'Dark mode' }}</span>
        </button>
        <RouterLink to="/profile" class="focus-ring account-chip flex items-center gap-3 rounded-xl p-2 cursor-pointer">
          <span class="account-avatar grid h-9 w-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-white" aria-hidden="true">{{ userInitials }}</span>
          <span class="min-w-0">
            <span class="block truncate text-sm font-medium text-slate-200">{{ userLabel }}</span>
            <span class="block text-[11px] uppercase tracking-wider text-slate-500">{{ authStore.user?.role || 'member' }}</span>
          </span>
        </RouterLink>
      </div>
    </aside>

    <!-- Main Content -->
    <main
      id="main-content"
      tabindex="-1"
      class="relative z-[1] flex-1 min-w-0 overflow-auto"
      :class="{ 'p-4 sm:p-6 lg:p-10': isStagedLayout }"
    >
      <div
        v-if="!isFullscreenLayout"
        class="mb-5 flex items-center gap-3 lg:hidden"
      >
        <button
          ref="mobileNavToggleRef"
          type="button"
          class="focus-ring icon-btn p-2 rounded-md text-slate-300 hover:text-slate-100 transition-colors"
          aria-label="Open navigation menu"
          aria-controls="mobile-navigation"
          :aria-expanded="isMobileNavOpen"
          @click="isMobileNavOpen = true"
        >
          <PhList size="18" weight="bold" aria-hidden="true" />
        </button>
        <!-- Location indicator, not a heading - each page already renders its own
             h1 via BasePageHeader. A second h1 here would give mobile screen-reader
             users two different "main heading" announcements per page. -->
        <p class="text-sm font-medium text-slate-200">{{ currentPageTitle }}</p>
      </div>
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="page" mode="out-in">
          <div
            :key="viewRoute.path"
            :class="{ 'page-stage': isStagedLayout, 'mx-auto max-w-[1400px]': !isFullscreenLayout }"
          >
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<style>
body {
  background: rgb(var(--canvas));
}

/* Visually hidden until focused - lets keyboard users jump past the sidebar
   nav (9+ links) straight to page content instead of tabbing through it on
   every single page. */
.skip-link {
  position: fixed;
  top: -100%;
  left: 1rem;
  z-index: 100;
  padding: 0.6rem 1rem;
  border-radius: 0.5rem;
  background: rgb(var(--brand-600));
  color: white;
  font-size: 0.875rem;
  font-weight: 500;
  transition: top 150ms ease;
}

.skip-link:focus {
  top: 1rem;
}

.shell-sidebar {
  position: sticky;
  background:
    linear-gradient(180deg, rgb(var(--brand-500) / 0.06), transparent 30%),
    rgb(var(--canvas) / 0.72);
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  border-right: 1px solid rgb(var(--border-subtle));
}

/* Hairline that glows where the sidebar meets the content. */
.shell-sidebar::after {
  content: '';
  position: absolute;
  top: 0;
  right: -1px;
  width: 1px;
  height: 100%;
  background: linear-gradient(180deg, transparent, rgb(var(--brand-400) / 0.45) 30%, rgb(var(--brand-alt-400) / 0.35) 70%, transparent);
  pointer-events: none;
}

.shell-footer {
  border-top: 1px solid rgb(var(--border-subtle));
  padding-top: 0.75rem;
}

.shell-drawer {
  background: rgb(var(--canvas) / 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-right: 1px solid rgb(var(--border-default));
}

.nav-link {
  position: relative;
  isolation: isolate;
  transition: color var(--dur-fast) ease;
}

/* Hover/active fill lives on a pseudo-element so it can scale in. */
.nav-link::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  background: rgb(var(--surface-raised) / 0.6);
  opacity: 0;
  transform: scale(0.94);
  transition: opacity var(--dur) var(--ease-out), transform var(--dur) var(--ease-spring);
}

.nav-link:hover::before {
  opacity: 1;
  transform: scale(1);
}

.nav-icon {
  transition: transform var(--dur) var(--ease-spring), color var(--dur-fast) ease;
}

.nav-link:hover .nav-icon {
  transform: translateX(2px) scale(1.12);
}

.nav-active {
  color: rgb(var(--slate-50));
}

.nav-active::before {
  opacity: 1;
  transform: scale(1);
  background:
    linear-gradient(90deg, rgb(var(--brand-500) / 0.18), rgb(var(--brand-alt-500) / 0.08) 70%, transparent);
  box-shadow: inset 0 0 0 1px rgb(var(--brand-400) / 0.18);
}

/* Glowing indicator bar that grows in on the active item. */
.nav-active::after {
  content: '';
  position: absolute;
  left: 0;
  top: 22%;
  bottom: 22%;
  width: 3px;
  border-radius: 9999px;
  background: linear-gradient(180deg, rgb(var(--brand-400)), rgb(var(--brand-alt-400)));
  box-shadow: 0 0 12px rgb(var(--brand-400) / 0.8);
  animation: nav-indicator-in 420ms var(--ease-spring) backwards;
}

@keyframes nav-indicator-in {
  from { transform: scaleY(0); opacity: 0; }
}

.nav-active .nav-icon {
  color: rgb(var(--brand-400));
  filter: drop-shadow(0 0 6px rgb(var(--brand-400) / 0.6));
}

.theme-toggle-icon {
  transition: transform 600ms var(--ease-spring);
}

.theme-toggle-icon.is-light {
  transform: rotate(360deg);
}

.account-chip {
  border: 1px solid rgb(var(--border-subtle));
  background: rgb(var(--surface) / 0.55);
  transition: border-color var(--dur) var(--ease-out), background-color var(--dur) var(--ease-out);
}

.account-chip:hover {
  border-color: rgb(var(--brand-400) / 0.35);
  background: rgb(var(--surface-raised) / 0.6);
}

.account-avatar {
  background: linear-gradient(135deg, rgb(var(--brand-500)), rgb(var(--brand-alt-500)) 60%, rgb(var(--brand-pink-500)));
  box-shadow: 0 0 0 2px rgb(var(--canvas)), 0 0 0 3px rgb(var(--brand-400) / 0.4);
}

.scrim-enter-active {
  transition: opacity var(--dur) var(--ease-out);
}

.scrim-leave-active {
  transition: opacity 180ms var(--ease-in);
}

.scrim-enter-from,
.scrim-leave-to {
  opacity: 0;
}
</style>
