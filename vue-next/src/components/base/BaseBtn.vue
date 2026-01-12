<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary' // primary, secondary, danger
  },
  label: String
})
</script>

<template>
  <button 
    class="px-5 py-2.5 rounded-lg font-medium transition-all duration-200 focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed"
    :class="{
      'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20 focus:ring-indigo-500': variant === 'primary',
      'bg-slate-800 hover:bg-slate-700 text-slate-200 focus:ring-slate-500': variant === 'secondary',
      'bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 focus:ring-red-500': variant === 'danger'
    }"
  >
    <slot>{{ label }}</slot>
  </button>
</template>
