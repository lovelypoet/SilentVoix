<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  title: {
    type: String,
    required: true
  },
  // Widen for content-heavy modals (previews, stats tables) vs. the default
  // confirmation-dialog width.
  maxWidth: {
    type: String,
    default: 'max-w-md' // Tailwind max-w-* class
  }
})

const emit = defineEmits(['update:modelValue'])

const panelRef = ref(null)
const titleId = `modal-title-${Math.random().toString(36).slice(2, 9)}`
let previouslyFocused = null

const close = () => emit('update:modelValue', false)

const focusableInPanel = () => {
  if (!panelRef.value) return []
  return Array.from(
    panelRef.value.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')
  )
}

const onKeydown = (event) => {
  if (event.key === 'Escape') {
    event.stopPropagation()
    close()
    return
  }
  if (event.key !== 'Tab') return

  const focusable = focusableInPanel()
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

watch(
  () => props.modelValue,
  async (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) {
      previouslyFocused = document.activeElement
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      focusableInPanel()[0]?.focus()
    } else {
      document.removeEventListener('keydown', onKeydown)
      previouslyFocused?.focus?.()
      previouslyFocused = null
    }
  }
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <div
    v-if="modelValue"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6"
    @click.self="close"
  >
    <div
      ref="panelRef"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      class="w-full rounded-xl border border-[rgb(var(--border-default))] bg-[rgb(var(--surface))] p-6 shadow-2xl relative"
      :class="maxWidth"
    >
      <button
        type="button"
        class="focus-ring absolute top-4 right-4 text-slate-400 hover:text-slate-100"
        aria-label="Close dialog"
        @click="close"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <h2 :id="titleId" class="text-xl font-semibold text-slate-100 mb-2 pr-8">{{ title }}</h2>

      <slot />

      <div v-if="$slots.footer" class="flex justify-end gap-3 pt-4 mt-4 border-t border-[rgb(var(--border-default))]">
        <slot name="footer" />
      </div>
    </div>
  </div>
</template>
