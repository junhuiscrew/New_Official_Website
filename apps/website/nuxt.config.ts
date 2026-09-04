// 配置用途：Public Website 的最小 Nuxt SSR 基线，不包含最终首页设计。
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  ssr: true,
  css: ['~/assets/css/main.css'],
  routeRules: {
    '/': { redirect: { to: '/zh-cn/', statusCode: 308 } },
    '/api/**': { proxy: 'http://api:8000/api/**' },
  },
  runtimeConfig: {
    apiInternalBase: 'http://api:8000/api/v1',
    public: {
      siteUrl: 'https://junhuiscrewbarrel.com',
      apiBase: '/api/v1',
    },
  },
  typescript: {
    strict: true,
    typeCheck: true,
  },
})
