import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Vite 8 使用 Rolldown，manualChunks 需要是函数
        manualChunks(id) {
          // React 核心库
          if (id.includes('node_modules/react/') || 
              id.includes('node_modules/react-dom/') || 
              id.includes('node_modules/react-router-dom/')) {
            return 'vendor-react';
          }
          // PDF 相关库（较大）
          if (id.includes('node_modules/react-pdf/') ||
              id.includes('node_modules/pdfjs-dist/')) {
            return 'vendor-pdf';
          }
          // 状态管理
          if (id.includes('node_modules/zustand/')) {
            return 'vendor-zustand';
          }
          // Markdown 渲染
          if (id.includes('node_modules/react-markdown/')) {
            return 'vendor-markdown';
          }
          // 其他 node_modules 依赖
          if (id.includes('node_modules/')) {
            return 'vendor';
          }
        },
      },
    },
    // chunk 大小警告阈值设为 500KB
    chunkSizeWarningLimit: 500,
  },
})
