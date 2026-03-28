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
          light: '#f5f0e8',      // Expiration warning backgrounds
          border: '#e6ddd0',     // Mocha alert card borders
          dark: '#8a7358',
        },
        // Terra - Terracotta/clay tones for warnings, highlights, and attention
        terra: {
          DEFAULT: '#c2715a',
          light: '#faf0ed',      // Low stock pill backgrounds
          dark: '#a85a44',
        },
        // Cream - Off-white backgrounds for pages and cards
        cream: {
          DEFAULT: '#faf8f4',    // Page background (warm cream)
          card: '#ffffff',        // Card surface (white on cream)
          surface: '#f9f8f3',     // Surface secondary (subtle card backgrounds)
          icon: '#f0eee6',        // Icon backgrounds, category chips
          pill: '#f7f5ee',        // Recipe ingredient pills, "in stock" badges
          dark: '#f0eee6',        // Deprecated alias for icon
        },
        // Warm - Neutral borders, dividers, and subtle text
        warm: {
          DEFAULT: '#d4d0c0',
          border: '#e8e5d8',     // Card borders, section dividers, input borders
          divider: '#f0efe8',    // Within-list item separators
          'btn-border': '#d4d0c0', // Secondary/outline button borders
          gray: '#8b8b7e',
        },
        // Ingredient pill background (per design system Section 2)
        'ingredient-pill-bg': '#f7f5ee',
        // Text colors (no pure black/white - following design system philosophy)
        text: {
          primary: '#2c2c2a',    // Headings, item names, primary content
          secondary: '#8b8b7e',  // Descriptions, metadata, timestamps, inactive tabs
          tertiary: '#a09f96',   // Section labels (uppercase), collapsed category counts
          muted: '#c4c3ba',      // Checkbox borders (unchecked), very low-priority indicators
        },
      },

      // Custom Border Radius Tokens
      borderRadius: {
        'card': '12px',       // For cards and panels
        'card-lg': '14px',    // Larger primary cards (tonight's dinner)
        'button': '12px',     // CTAs, "Add to meal plan"
        'button-sm': '8px',   // Filter chips, "Ate it", "Freeze"
        'input': '10px',      // Search bars, text inputs
        'pill': '6px',        // "in stock", "low", source labels (4-6px spec)
        'tag': '12px',        // Full-round for tags like "pescatarian", "japanese"
        'image-hero': '16px', // Hero images
        'image-card': '10px', // Card images
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

      // Font Sizes - Custom tokens for consistent typography
      fontSize: {
        'tiny': '10px',  // Bottom nav labels, badge text
      },
    },
  },
  plugins: [],
}
