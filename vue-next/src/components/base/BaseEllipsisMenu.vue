<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Popover from 'primevue/popover'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  panelClass: {
    type: String,
    default: ''
  },
  menuClass: {
    type: String,
    default: 'w-44 py-1'
  },
  // Screen readers only ever hear "…" otherwise - name what the menu is for
  // ("Row actions", "Model actions") when more than one lives on a page.
  label: {
    type: String,
    default: 'More actions'
  }
})

const panelRef = ref(null)
const isOpen = ref(false)
const instanceId = Symbol('BaseEllipsisMenu')

const handleGlobalOpen = (event) => {
  const openedId = event?.detail?.id
  if (!openedId || openedId === instanceId) return
  if (!isOpen.value) return
  panelRef.value?.hide()
  isOpen.value = false
}

onMounted(() => {
  window.addEventListener('sv-ellipsis-open', handleGlobalOpen)
})

onBeforeUnmount(() => {
  window.removeEventListener('sv-ellipsis-open', handleGlobalOpen)
})

const close = () => {
  panelRef.value?.hide()
  isOpen.value = false
}

const toggle = (event) => {
  if (props.disabled) return
  if (isOpen.value) {
    close()
    return
  }
  window.dispatchEvent(new CustomEvent('sv-ellipsis-open', { detail: { id: instanceId } }))
  panelRef.value?.show(event)
  isOpen.value = true
}

const handleHide = () => {
  isOpen.value = false
}
</script>

<template>
  <button
    type="button"
    class="focus-ring icon-btn h-8 w-8 rounded-md text-slate-300 hover:text-slate-100 disabled:opacity-50"
    :disabled="disabled"
    :aria-label="label"
    aria-haspopup="menu"
    :aria-expanded="isOpen"
    @click.stop="toggle"
  >
    &hellip;
  </button>
  <Popover
    ref="panelRef"
    :dismissable="true"
    :show-close-icon="false"
    :class="panelClass || '!bg-[rgb(var(--surface))] !border !border-[rgb(var(--border-default))] !text-slate-100 !shadow-2xl'"
    @hide="handleHide"
  >
    <div :class="menuClass">
      <slot name="menu" :close="close" />
    </div>
  </Popover>
</template>
