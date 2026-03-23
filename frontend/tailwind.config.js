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
          DEFAULT: '#5C6F47', // Main olive green
          light: '#7A8F5E',
          dark: '#4A5A38',
        },
        // Mocha - Browns for surfaces, cards, and secondary elements
        mocha: {
          DEFAULT: '#6B5544',
          light: '#8B7265',
          dark: '#4A3B2F',
        },
        // Terra - Terracotta/clay tones for warnings, highlights, and attention
        terra: {
          DEFAULT: '#A0522D',
          light: '#C17B56',
          dark: '#7A3E1F',
        },
        // Cream - Off-white backgrounds for pages and cards
        cream: {
          DEFAULT: '#F8F6F0',
          dark: '#EDE9DD',
        },
        // Warm - Neutral borders, dividers, and subtle text
        warm: {
          DEFAULT: '#D4C5B0',
          border: '#C9B99C',
          gray: '#8C8174',
        },
        // Text colors (no pure black/white - following design system philosophy)
        text: {
          primary: '#2B2621',   // Almost black, warm undertone
          secondary: '#5A544D', // Medium warm gray
          tertiary: '#8C8174',  // Light warm gray
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
