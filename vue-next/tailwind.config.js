/** @type {import('tailwindcss').Config} */

// Every brand and status color resolves to a CSS variable declared in src/style.css.
// The `<alpha-value>` placeholder keeps Tailwind's slash-opacity syntax working,
// so `bg-accent-500/10` and `text-success-300` behave like any built-in color.
const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]

const tokenScale = (name) =>
  Object.fromEntries(
    SHADES.map((shade) => [shade, `rgb(var(--${name}-${shade}) / <alpha-value>)`])
  )

export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand accent (cyan) and its companions for gradients/glows (violet, pink).
        brand: tokenScale('brand'),
        'brand-alt': tokenScale('brand-alt'),
        'brand-pink': tokenScale('brand-pink'),
        // Status colors. Semantic names so intent survives the next recolor.
        success: tokenScale('success'),
        warning: tokenScale('warning'),
        danger: tokenScale('danger'),
        // Overrides Tailwind's built-in slate with the CSS-variable version in
        // style.css, so every existing bg-slate-900/text-slate-400/etc. across
        // the app inverts automatically under [data-theme="light"] - this is
        // the mechanism the light theme rides on, see style.css for the why.
        slate: tokenScale('slate'),
      },
      fontFamily: {
        display: ['"Space Grotesk"', '"DM Sans"', 'sans-serif'],
      },
      boxShadow: {
        'brand-glow': '0 18px 40px -18px rgb(var(--brand-500) / 0.55)',
      },
    },
  },
  plugins: [],
}
