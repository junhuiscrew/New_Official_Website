// 配置用途：Admin CMS 的最小 Nuxt SSR 壳，Phase 3.1 不实现登录和完整 CMS。
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  ssr: true,
  css: ['~/assets/css/main.css'],
  typescript: {
    strict: true,
    typeCheck: true,
  },
})
