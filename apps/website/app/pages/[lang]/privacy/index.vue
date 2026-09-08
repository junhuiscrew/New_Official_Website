<!-- 页面用途：服务端展示当前语言已发布的隐私政策。 -->
<script setup lang="ts">
import { computed } from 'vue'

import PrivacyMarkdown from '~/components/PrivacyMarkdown.vue'
import { normalizeLocale } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import { SITE_URL } from '~/site-config'
import type { PublicPrivacyPolicyDto } from '~/types/public'
import { publicRequestStatus } from '~/utils/publicRequest'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

const route = useRoute()
const api = useApi()
const locale = normalizeLocale(route.params.lang)
const labels = computed(() => ui[locale])
const { data: response, error } = await useAsyncData(`privacy:${locale}`, () =>
  api<Envelope<PublicPrivacyPolicyDto>>(`/public/privacy/${locale}`),
)

// 后端用 404 统一表达未初始化、禁用、无 current、未生效或缺少任一翻译；SSR 必须保留该状态。
if (error.value && publicRequestStatus(error.value) === 404) {
  throw createError({ statusCode: 404, statusMessage: 'Privacy policy not found' })
}
if (error.value || !response.value?.data) {
  throw createError({ statusCode: 500, statusMessage: 'Privacy policy unavailable' })
}

const policy = computed(() => response.value!.data)
const effectiveLabel = computed(() => {
  const effectiveAt = new Date(policy.value.effective_at)
  if (Number.isNaN(effectiveAt.getTime())) return policy.value.effective_at
  return new Intl.DateTimeFormat(locale === 'zh-cn' ? 'zh-CN' : 'en', {
    dateStyle: 'long',
    timeZone: 'UTC',
  }).format(effectiveAt)
})

/** 把后端固定同站路径转换为正式站绝对 URL，异常值不会进入 Head。 */
function officialUrl(candidate: string, fallbackPath: string): string {
  try {
    const parsed = new URL(candidate, SITE_URL)
    return parsed.origin === SITE_URL ? parsed.href : new URL(fallbackPath, SITE_URL).href
  } catch {
    return new URL(fallbackPath, SITE_URL).href
  }
}

// canonical、双语 hreflang 与业务 robots 均来自当前公开政策 DTO，并固定落在正式站域名。
useHead(() => ({
  htmlAttrs: { lang: locale === 'zh-cn' ? 'zh-CN' : 'en' },
  title: policy.value.title,
  meta: [
    {
      name: 'robots',
      content: `${policy.value.robots.index ? 'index' : 'noindex'},${policy.value.robots.follow ? 'follow' : 'nofollow'}`,
    },
  ],
  link: [
    {
      rel: 'canonical',
      href: officialUrl(policy.value.canonical_url, policy.value.canonical_path),
    },
    ...Object.entries(policy.value.alternates)
      .filter(([hreflang]) => hreflang === 'zh-CN' || hreflang === 'en')
      .map(([hreflang, path]) => ({
        rel: 'alternate' as const,
        hreflang,
        href: officialUrl(path, hreflang === 'zh-CN' ? '/zh-cn/privacy/' : '/en/privacy/'),
      })),
  ],
}))
</script>

<template>
  <article class="privacy-page">
    <div class="public-container privacy-page__content">
      <header class="privacy-page__header">
        <h1>{{ policy.title }}</h1>
        <dl class="privacy-page__metadata">
          <div>
            <dt>{{ labels.privacy.version }}</dt>
            <dd>{{ policy.version_label }}</dd>
          </div>
          <div>
            <dt>{{ labels.privacy.effectiveAt }}</dt>
            <dd>{{ effectiveLabel }}</dd>
          </div>
        </dl>
      </header>

      <PrivacyMarkdown :markdown="policy.body_markdown" />
    </div>
  </article>
</template>

<style scoped>
.privacy-page {
  padding-block: var(--space-12) var(--space-20);
  background: var(--color-neutral-50);
}

.privacy-page__content {
  max-width: 56rem;
}

.privacy-page__header {
  margin-block-end: var(--space-10);
  padding-block-end: var(--space-6);
  border-block-end: var(--border-subtle);
}

.privacy-page__header h1 {
  margin: 0;
  color: var(--color-navy-950);
}

.privacy-page__metadata {
  margin: var(--space-5) 0 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4) var(--space-8);
}

.privacy-page__metadata div {
  display: flex;
  gap: var(--space-2);
}

.privacy-page__metadata dt {
  color: var(--color-neutral-600);
}

.privacy-page__metadata dd {
  margin: 0;
  color: var(--color-navy-900);
  font-weight: 700;
}

.privacy-page :deep(.privacy-markdown) {
  display: grid;
  gap: var(--space-4);
  color: var(--color-neutral-800);
  line-height: var(--line-height-relaxed);
}

.privacy-page :deep(.privacy-markdown > *) {
  margin: 0;
}

.privacy-page :deep(.privacy-markdown__heading) {
  margin-block-start: var(--space-6);
  color: var(--color-navy-900);
}

.privacy-page :deep(blockquote) {
  padding: var(--space-4) var(--space-5);
  border-inline-start: 3px solid var(--color-blue-600);
  background: var(--color-white);
}

.privacy-page :deep(pre) {
  max-width: 100%;
  padding: var(--space-4);
  overflow-x: auto;
  background: var(--color-navy-950);
  color: var(--color-neutral-100);
}
</style>
