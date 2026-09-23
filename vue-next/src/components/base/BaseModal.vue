<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { PhX } from '@phosphor-icons/vue'

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
  <Transition name="modal-scrim">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md px-4 py-6"
      @click.self="close"
    >
      <Transition name="modal-panel" appear>
        <div
          ref="panelRef"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          class="modal-panel w-full rounded-2xl border border-[rgb(var(--border-default))] bg-[rgb(var(--surface-raised))] p-6 shadow-2xl relative"
          :class="maxWidth"
        >
          <button
            type="button"
            class="focus-ring icon-btn absolute top-4 right-4 grid h-8 w-8 place-items-center rounded-md text-slate-400 hover:text-slate-100"
            aria-label="Close dialog"
            @click="close"
          >
            <PhX size="16" weight="bold" aria-hidden="true" />
          </button>

          <h2 :id="titleId" class="text-lg font-semibold tracking-tight text-slate-100 mb-3 pr-8">{{ title }}</h2>

          <slot />

          <div v-if="$slots.footer" class="flex flex-wrap justify-end gap-2.5 pt-5 mt-5 border-t border-[rgb(var(--border-default))]">
            <slot name="footer" />
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.modal-scrim-enter-active,
.modal-scrim-leave-active {
  transition: opacity 180ms ease;
}
.modal-scrim-enter-from,
.modal-scrim-leave-to {
  opacity: 0;
}

.modal-panel-enter-active {
  transition: opacity 260ms var(--ease-out), transform 420ms var(--ease-spring);
}
.modal-panel-leave-active {
  transition: opacity 160ms var(--ease-in), transform 160ms var(--ease-in);
}
.modal-panel-enter-from {
  opacity: 0;
  transform: translateY(18px) scale(0.94);
}
.modal-panel-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.modal-panel {
  box-shadow: 0 40px 80px -30px rgb(0 0 0 / 0.7), 0 0 0 1px rgb(var(--brand-400) / 0.06);
}

/* Brand gradient hairline across the top edge. */
.modal-panel::before {
  content: '';
  position: absolute;
  top: -1px;
  left: 12%;
  right: 12%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgb(var(--brand-400)), rgb(var(--brand-alt-400)), transparent);
}
</style>
