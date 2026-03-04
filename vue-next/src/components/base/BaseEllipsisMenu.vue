<script setup>
import { ref } from 'vue'
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
  }
})

const panelRef = ref(null)

const toggle = (event) => {
  if (props.disabled) return
  panelRef.value?.toggle(event)
}

const close = () => {
  panelRef.value?.hide()
}
</script>

<template>
  <button
    type="button"
    class="h-8 w-8 rounded-md border border-slate-700 bg-slate-900/70 text-slate-200 hover:bg-slate-800 disabled:opacity-50"
    :disabled="disabled"
    @click.stop="toggle"
  >
    &hellip;
  </button>
  <Popover
    ref="panelRef"
    :dismissable="true"
    :show-close-icon="false"
    :class="panelClass || '!bg-slate-950 !border !border-slate-700 !text-slate-100 !shadow-2xl'"
  >
    <div :class="menuClass">
      <slot name="menu" :close="close" />
    </div>
  </Popover>
</template>
