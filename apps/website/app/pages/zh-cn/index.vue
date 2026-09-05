<!-- 页面用途：简体中文最终首页，通过单次 SSR 聚合请求取得全部公开内容。 -->
<script setup lang="ts">
import { computed } from 'vue'

import type { HomeDto } from '~/types/public'

interface HomeEnvelope {
  success: boolean
  data: HomeDto | null
  error: unknown | null
}

const locale = 'zh-cn'
const api = useApi()

// 单次请求由 Nuxt 写入 SSR payload，首页各区块不再发起独立客户端请求。
const { data: response, error } = await useAsyncData(`home:${locale}`, () =>
  api<HomeEnvelope>(`/public/home/${locale}`),
)
if (error.value) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Homepage not found' : 'Homepage unavailable',
  })
}
if (!response.value?.success || !response.value.data) {
  throw createError({ statusCode: 404, statusMessage: 'Homepage not found' })
}
const home = computed(() => response.value!.data!)
</script>

<template>
  <HomePage :locale="locale" :home="home" />
</template>
