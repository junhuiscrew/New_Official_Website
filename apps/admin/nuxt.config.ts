// 配置用途：Admin CMS 的 Phase 3.2 认证与 RBAC 基础壳，不包含完整 CMS。
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  ssr: true,
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      meta: [{ name: 'robots', content: 'noindex, nofollow' }],
    },
  },
  routeRules: {
    '/api/**': { proxy: 'http://api:8000/api/**' },
    '/**': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
  },
  runtimeConfig: {
    apiInternalBase: 'http://api:8000/api/v1',
    public: {
      apiBase: '/api/v1',
    },
  },
  typescript: {
    strict: true,
    typeCheck: true,
  },
})
