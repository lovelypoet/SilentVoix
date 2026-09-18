<script setup>
import { computed, useId } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: ''
  },
  label: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: 'text'
  },
  placeholder: {
    type: String,
    default: ''
  },
  // Optional explicit id. Falls back to a generated one so the label is
  // always programmatically associated with its input.
  id: {
    type: String,
    default: ''
  },
  hint: {
    type: String,
    default: ''
  },
  error: {
    type: String,
    default: ''
  }
})

defineEmits(['update:modelValue'])

const generatedId = useId()
const inputId = computed(() => props.id || `input-${generatedId}`)
const describedById = computed(() => {
  if (props.error) return `${inputId.value}-error`
  if (props.hint) return `${inputId.value}-hint`
  return undefined
})
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label
      v-if="label"
      :for="inputId"
      class="text-sm font-medium text-slate-400 ml-1"
    >{{ label }}</label>
    <input
      :id="inputId"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :aria-describedby="describedById"
      :aria-invalid="error ? 'true' : undefined"
      class="bg-[rgb(var(--surface))] border rounded-lg px-3.5 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus-visible:border-brand-500 focus-visible:ring-1 focus-visible:ring-brand-500 transition-colors duration-150"
      :class="error ? 'border-danger-500' : 'border-[rgb(var(--border-default))]'"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <p
      v-if="error"
      :id="`${inputId}-error`"
      class="text-xs text-danger-300 ml-1"
    >{{ error }}</p>
    <p
      v-else-if="hint"
      :id="`${inputId}-hint`"
      class="text-xs text-slate-500 ml-1"
    >{{ hint }}</p>
  </div>
</template>
