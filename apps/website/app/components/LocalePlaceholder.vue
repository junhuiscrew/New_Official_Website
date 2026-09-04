<!-- 组件职责：呈现非最终视觉的语言占位页及用户可见的直接说明。 -->
<script setup lang="ts">
import type { LocalePageConfig } from '../site-config'

const props = defineProps<{
  page: LocalePageConfig
}>()

// SEO/GEO 基线：所有关键信息由 SSR 输出，并与可见正文保持一致。
useHead({
  htmlAttrs: { lang: props.page.localeCode },
  title: props.page.title,
  meta: [
    { name: 'description', content: props.page.description },
    { name: 'robots', content: 'index, follow' },
  ],
  link: [
    { rel: 'canonical', href: props.page.canonical },
    ...Object.entries(props.page.alternates).map(([hreflang, href]) => ({
      rel: 'alternate' as const,
      type: 'text/html',
      hreflang,
      href,
    })),
  ],
})
</script>

<template>
  <main class="placeholder-shell">
    <section aria-labelledby="page-title" class="placeholder-content">
      <p class="phase-label">{{ page.phaseLabel }}</p>
      <h1 id="page-title">{{ page.heading }}</h1>
      <p class="direct-answer">{{ page.directAnswer }}</p>
      <nav aria-label="Language">
        <a href="/zh-cn/" lang="zh-CN" hreflang="zh-CN">简体中文</a>
        <a href="/en/" lang="en" hreflang="en">English</a>
      </nav>
    </section>
  </main>
</template>
