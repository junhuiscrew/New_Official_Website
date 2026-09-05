// 配置用途：Public Website 的最小 Nuxt SSR 基线，不包含最终首页设计。
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  // 停电或并行 QA 后可将生成目录指向隔离临时路径，避免复用被占用的构建缓存。
  buildDir: process.env.NUXT_BUILD_DIR || '.nuxt',
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
