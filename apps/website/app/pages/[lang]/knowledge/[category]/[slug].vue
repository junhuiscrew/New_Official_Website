<!-- 页面用途：SSR 展示带真实作者、审核、日期、GEO、来源和关系的 Knowledge Article。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicKnowledgeDetailDto } from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

const route = useRoute()
const api = useApi()
const locale = computed<LocaleSlug>(() => normalizeLocale(route.params.lang))
const labels = computed(() => ui[locale.value])
const category = computed(() => String(route.params.category ?? ''))
const slug = computed(() => String(route.params.slug ?? ''))
const requestKey = computed(
  () => `authority:knowledge:${locale.value}:${category.value}:${slug.value}`,
)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicKnowledgeDetailDto>>(
    `/public/knowledge/${locale.value}/${category.value}/${slug.value}`,
  ),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Knowledge article not found' : 'Knowledge unavailable',
  })
}
const page = computed(() => response.value!.data)
const visibleSources = computed(() =>
  page.value.sources.filter((source) => /^https?:\/\//i.test(source.url)),
)

// canonical、hreflang 与全部 Schema 由后端统一生成，页面仅执行安全序列化。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: page.value.seo.title,
  meta: [
    ...(page.value.seo.description
      ? [{ name: 'description', content: page.value.seo.description }]
      : []),
    { name: 'robots', content: page.value.seo.robots },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo.canonical },
    ...Object.entries(page.value.alternates ?? page.value.seo.hreflang ?? {}).map(
      ([hreflang, href]) => ({ rel: 'alternate' as const, hreflang, href }),
    ),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>

<template>
  <div class="authority-detail">
    <div class="public-container authority-detail__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="page.category.name"
      :title="page.translation.title"
      :summary="page.translation.summary || page.translation.title"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale, type: 'knowledge_article', slug: page.slug })"
      :secondary-label="labels.navigation.knowledge"
      :secondary-href="`/${locale}/knowledge/`"
    >
      <template #heading
        ><h1>{{ page.translation.title }}</h1></template
      >
    </PageHero>
    <article class="public-container authority-detail__body">
      <section class="authority-detail__metadata" aria-label="Article authority metadata">
        <a class="eyebrow" :href="page.category.url">{{ page.category.name }}</a>
        <dl>
          <div>
            <dt>{{ labels.content.author }}</dt>
            <dd>
              {{ page.author.name }}
              <span v-if="page.author.job_title"> — {{ page.author.job_title }}</span>
            </dd>
          </div>
          <div v-if="page.reviewer">
            <dt>{{ labels.content.reviewer }}</dt>
            <dd>
              {{ page.reviewer.name }}
              <span v-if="page.reviewer.job_title"> — {{ page.reviewer.job_title }}</span>
            </dd>
          </div>
          <div v-if="page.published_at">
            <dt>{{ labels.content.published }}</dt>
            <dd>
              <time :datetime="page.published_at">{{ page.published_at }}</time>
            </dd>
          </div>
          <div v-if="page.updated_at">
            <dt>{{ labels.content.updated }}</dt>
            <dd>
              <time :datetime="page.updated_at">{{ page.updated_at }}</time>
            </dd>
          </div>
          <div v-if="page.last_reviewed_at">
            <dt>{{ labels.content.lastReviewed }}</dt>
            <dd>
              <time :datetime="page.last_reviewed_at">{{ page.last_reviewed_at }}</time>
            </dd>
          </div>
        </dl>
        <p v-if="page.author.short_bio">{{ page.author.short_bio }}</p>
      </section>

      <GeoAnswer :locale="locale" :geo="page.geo" />

      <section class="authority-detail__article-body" aria-label="Article body">
        <p class="body-markdown">{{ page.translation.body_markdown }}</p>
      </section>

      <section v-if="visibleSources.length" class="authority-detail__sources">
        <h2>{{ labels.content.sources }}</h2>
        <ol>
          <li v-for="source in visibleSources" :key="source.url">
            <a :href="source.url" rel="noopener noreferrer">{{ source.title }}</a>
            <dl>
              <div v-if="source.publisher">
                <dt>{{ labels.content.publisher }}</dt>
                <dd>{{ source.publisher }}</dd>
              </div>
              <div v-if="source.publication_date">
                <dt>{{ labels.content.published }}</dt>
                <dd>
                  <time :datetime="source.publication_date">{{ source.publication_date }}</time>
                </dd>
              </div>
              <div v-if="source.source_type">
                <dt>{{ labels.content.sourceType }}</dt>
                <dd>{{ source.source_type }}</dd>
              </div>
            </dl>
          </li>
        </ol>
      </section>

      <FAQAccordion :locale="locale" :items="page.faqs" />
      <!-- PublicRelationLinks 旧组件由更严格的 RelationLinks 白名单实现替代。 -->
      <RelationLinks
        :locale="locale"
        :relations="page.relations"
        :groups="['products', 'materials', 'technologies', 'applications', 'solutions', 'cases']"
      />
    </article>
    <RfqCta :locale="locale" source-type="knowledge_article" :source-slug="page.slug" />
  </div>
</template>

<style scoped>
.authority-detail__breadcrumb {
  padding-block: var(--space-4);
}

.authority-detail__body {
  padding-block: var(--space-12) var(--space-16);
  display: grid;
  gap: var(--space-10);
}

.authority-detail__metadata,
.authority-detail__metadata dl,
.authority-detail__sources dl {
  display: grid;
  gap: var(--space-3);
}

.authority-detail__metadata dl,
.authority-detail__sources dl {
  margin: 0;
}

.authority-detail__metadata dl > div,
.authority-detail__sources dl > div {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.authority-detail__metadata dt,
.authority-detail__metadata dd,
.authority-detail__sources dt,
.authority-detail__sources dd {
  margin: 0;
}

.authority-detail__article-body {
  max-width: 54rem;
}

.body-markdown {
  color: var(--color-neutral-700);
  line-height: var(--line-height-relaxed);
  white-space: pre-line;
}

.authority-detail__sources ol {
  padding-inline-start: var(--space-6);
}

.authority-detail__sources li + li {
  margin-block-start: var(--space-5);
}
</style>
