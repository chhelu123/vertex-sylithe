import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React — tiny, always cached
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Map stack — leaflet is large (~140 kB gzipped), isolate it
          // Charts
          'vendor-charts': ['recharts'],
          // Animation
          'vendor-motion': ['framer-motion'],
          // Geo utilities (large — georaster alone is ~500 kB)
          // UI / icon libraries
          'vendor-ui': ['lucide-react', 'react-icons', '@radix-ui/react-label', '@radix-ui/react-radio-group', '@radix-ui/react-select', '@radix-ui/react-separator', '@radix-ui/react-slot', '@radix-ui/react-switch', '@radix-ui/react-tooltip'],
        },
      },
    },
    // Raise the warning threshold — vendor chunks will be large by design
    chunkSizeWarningLimit: 1000,
  },
})
