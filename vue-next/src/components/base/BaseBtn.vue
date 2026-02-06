<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary' // primary, secondary, danger, amber
  },
  label: String
})
</script>

<template>
  <button 
    class="px-5 py-2.5 rounded-lg font-medium transition-all duration-200 focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed"
    :class="{
      'btn-primary': variant === 'primary',
      'btn-secondary': variant === 'secondary',
      'btn-danger': variant === 'danger',
      'btn-amber': variant === 'amber'
    }"
  >
    <slot>{{ label }}</slot>
  </button>
</template>

<style scoped>
.btn-primary {
  --btn-hue: 174; /* teal-600 hue */
  --btn-saturation: 62%;
  --btn-lightness: 45%;
  background: hsl(var(--btn-hue) var(--btn-saturation) var(--btn-lightness));
  color: white;
  box-shadow: 0 10px 15px -3px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.2), 0 4px 6px -4px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.2);
  transition: all 300ms ease; /* Adjusted transition for smoother effect */
  
  /* Focus ring for primary button */
  --tw-ring-color: hsl(var(--btn-hue) var(--btn-saturation) var(--btn-lightness));
}

.btn-primary:hover,
.btn-primary:focus-visible {
  --btn-hue: 186; /* Shift hue on hover/focus */
  --btn-saturation: 70%;
  --btn-lightness: 55%; /* teal-400 lightness */
  box-shadow: 0 10px 15px -3px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.3), 0 4px 6px -4px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.3);
}

.btn-amber {
  --btn-hue: 42; /* soft sand hue */
  --btn-saturation: 45%;
  --btn-lightness: 58%;
  background: hsl(var(--btn-hue) var(--btn-saturation) var(--btn-lightness));
  color: white;
  box-shadow: 0 10px 15px -3px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.2), 0 4px 6px -4px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.2);
  transition: all 300ms ease;
  
  --tw-ring-color: hsl(var(--btn-hue) var(--btn-saturation) var(--btn-lightness));
}

.btn-amber:hover,
.btn-amber:focus-visible {
  --btn-hue: 38; /* warmer sand on hover */
  --btn-saturation: 55%;
  --btn-lightness: 62%;
  box-shadow: 0 10px 15px -3px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.3), 0 4px 6px -4px hsl(var(--btn-hue) var(--btn-saturation) calc(var(--btn-lightness) + 10%)/0.3);
}

.btn-secondary {
  background: linear-gradient(180deg, rgba(14, 116, 144, 0.18), rgba(15, 23, 42, 0.2));
  color: #d5e6e6;
  border: 1px solid rgba(45, 212, 191, 0.25);
  box-shadow: 0 10px 15px -3px rgba(45, 212, 191, 0.12), 0 4px 6px -4px rgba(45, 212, 191, 0.12);
  transition: all 300ms ease;
  --tw-ring-color: rgba(45, 212, 191, 0.6);
}

.btn-secondary:hover,
.btn-secondary:focus-visible {
  background: linear-gradient(180deg, rgba(20, 184, 166, 0.22), rgba(15, 23, 42, 0.2));
  color: white;
  box-shadow: 0 10px 15px -3px rgba(45, 212, 191, 0.22), 0 4px 6px -4px rgba(45, 212, 191, 0.22);
}

.btn-danger {
  background: rgba(248, 113, 113, 0.12);
  color: #fca5a5;
  border: 1px solid rgba(248, 113, 113, 0.25);
  transition: all 300ms ease;
  --tw-ring-color: rgba(248, 113, 113, 0.55);
}

.btn-danger:hover,
.btn-danger:focus-visible {
  background: rgba(248, 113, 113, 0.2);
  color: #fecaca;
  box-shadow: 0 10px 15px -3px rgba(248, 113, 113, 0.2), 0 4px 6px -4px rgba(248, 113, 113, 0.2);
}
</style>
