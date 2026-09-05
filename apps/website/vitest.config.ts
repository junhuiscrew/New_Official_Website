// 配置用途：让 Website Vitest 在轻量 DOM 环境中真实挂载 Vue 单文件组件。
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '~': new URL('./app', import.meta.url).pathname,
      '@': new URL('./app', import.meta.url).pathname,
    },
  },
  test: {
    environment: 'happy-dom',
  },
})
