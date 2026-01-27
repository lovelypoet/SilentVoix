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
      'btn-primary': variant === 'primary',
      'bg-slate-800 hover:bg-slate-700 text-slate-200 focus:ring-slate-500': variant === 'secondary',
      'bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 focus:ring-red-500': variant === 'danger'
    }"
  >
    <slot>{{ label }}</slot>
  </button>
</template>

<style scoped>
.btn-primary {
  --btn-hue: 246; /* indigo-600 hue */
  --btn-saturation: 69%;
  --btn-lightness: 51%;
  background: hsl(var(--btn-hue) var(--btn-saturation) var(--btn-lightness));
  color: white;
  box-shadow: 0 10px 15px -3px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.2), 0 4px 6px -4px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.2);
  transition: all 300ms ease; /* Adjusted transition for smoother effect */
  
  /* Focus ring for primary button */
  --tw-ring-color: hsl(var(--btn-hue) var(--btn-saturation) var(--btn-lightness));
}

.btn-primary:hover,
.btn-primary:focus-visible {
  --btn-hue: 260; /* Shift hue on hover/focus */
  --btn-saturation: 80%;
  --btn-lightness: 67%; /* indigo-500 lightness */
  box-shadow: 0 10px 15px -3px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.3), 0 4px 6px -4px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.3);
}
</style>
