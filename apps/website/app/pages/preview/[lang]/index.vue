<!-- 页面用途：通过 Admin 同源会话服务端读取首页草稿，并渲染不可缓存、不可索引的完整布局预览。 -->
<script setup lang="ts">
import { computed } from 'vue'

import type { HomeDto, LocaleSlug } from '~/types/public'

interface HomeEnvelope {
  success: boolean
  data: HomeDto | null
  error: unknown | null
}

const route = useRoute()
const localeSlug = route.params.lang
if (localeSlug !== 'zh-cn' && localeSlug !== 'en') {
  throw createError({ statusCode: 404, statusMessage: 'Preview locale not found' })
}
const pageLocale = localeSlug as LocaleSlug
const locale = pageLocale === 'zh-cn' ? 'zh-CN' : 'en'
const api = useApi()
const requestHeaders = useRequestHeaders(['cookie'])

// 预览安全头由 SSR 响应直接写入，不能依赖浏览器脚本或查询参数。
const previewResponseHeaders = {
  'Cache-Control': 'private, no-store',
  'X-Robots-Tag': 'noindex, nofollow',
}
useResponseHeader('Cache-Control').value = previewResponseHeaders['Cache-Control']
useResponseHeader('X-Robots-Tag').value = previewResponseHeaders['X-Robots-Tag']

const { data: response, error } = await useAsyncData(`homepage-preview:${locale}`, () =>
  api<HomeEnvelope>(`/presentation/homepage/${locale}/preview`, {
    headers: requestHeaders,
  }),
)
if (error.value) {
  const statusCode =
    error.value?.statusCode === 401 ? 401 : error.value?.statusCode === 403 ? 403 : 500
  throw createError({ statusCode, statusMessage: 'Authenticated preview unavailable' })
}
if (!response.value?.success || !response.value.data) {
  throw createError({ statusCode: 404, statusMessage: 'Homepage preview not found' })
}
const home = computed(() => response.value!.data!)

useHead({
  title: `${home.value.company?.company_name || 'Junhui'} · Preview`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>

<template>
  <HomePage :locale="pageLocale" :home="home" :preview="true" />
</template>
