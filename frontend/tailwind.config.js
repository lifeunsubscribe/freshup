/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // FreshUp Custom Color Palette - Earth Tones
      colors: {
        // Olive - Primary greens for buttons, accents, and active states
        olive: {
          DEFAULT: '#6b7f4a',
          light: '#8a9b6e',
          dark: '#4a6332',
        },
        // Mocha - Browns for surfaces, cards, and secondary elements
        mocha: {
          DEFAULT: '#a08b6e',
          light: '#b5a48e',
          dark: '#8a7358',
        },
        // Terra - Terracotta/clay tones for warnings, highlights, and attention
        terra: {
          DEFAULT: '#c2715a',
          light: '#d4937f',
          dark: '#a85a44',
        },
        // Cream - Off-white backgrounds for pages and cards
        cream: {
          DEFAULT: '#faf8f4',
          dark: '#f0eee6',
        },
        // Warm - Neutral borders, dividers, and subtle text
        warm: {
          DEFAULT: '#d4d0c0',
          border: '#e8e5d8',
          gray: '#8b8b7e',
        },
        // Ingredient pill background (per design system Section 2)
        'ingredient-pill-bg': '#f7f5ee',
        // Text colors (no pure black/white - following design system philosophy)
        text: {
          primary: '#2c2c2a',
          secondary: '#8b8b7e',
          tertiary: '#a09f96',
        },
      },

      // Custom Border Radius Tokens
      borderRadius: {
        'card': '12px',    // For cards and panels
        'button': '8px',   // For buttons and interactive elements
        'pill': '9999px',  // For pill-shaped elements (fully rounded)
      },

      // System Font Stack - Native, performant fonts
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
      },

      // Line Heights (following design system specs for readability)
      lineHeight: {
        'tight': '1.25',
        'normal': '1.5',
        'relaxed': '1.75',
      },
    },
  },
  plugins: [],
}
