<!-- 页面用途：SSR 展示后端核验并授权公开的真实 Person 资料及其已发布文章。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicExpertDetailDto } from '~/types/public'
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
const slug = computed(() => String(route.params.slug ?? ''))
const requestKey = computed(() => `authority:expert:${locale.value}:${slug.value}`)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicExpertDetailDto>>(`/public/experts/${locale.value}/${slug.value}`),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Expert not found' : 'Expert profile unavailable',
  })
}
if (!response.value.data.is_real_person_verified)
  throw createError({ statusCode: 404, statusMessage: 'Expert not found' })
const page = computed(() => response.value!.data)

// Person、canonical、hreflang 和其他 Schema 只消费后端已核验输出。
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
  <div v-if="page.is_real_person_verified" class="authority-detail">
    <div class="public-container authority-detail__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="page.job_title"
      :title="page.name"
      :summary="page.short_bio || page.name"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale, type: 'author_expert', slug: page.slug })"
      :secondary-label="labels.authority.expertsTitle"
      :secondary-href="`/${locale}/experts/`"
      :media="page.profile_media"
    >
      <template #heading
        ><h1>{{ page.name }}</h1></template
      >
    </PageHero>
    <article class="public-container authority-detail__body">
      <section class="authority-detail__profile">
        <dl>
          <div v-if="page.job_title">
            <dt>{{ labels.authority.expertType }}</dt>
            <dd>{{ page.job_title }}</dd>
          </div>
          <div v-if="page.years_experience !== null">
            <dt>{{ labels.content.experience }}</dt>
            <dd>{{ page.years_experience }} {{ labels.content.years }}</dd>
          </div>
          <div v-if="page.public_email">
            <dt>{{ labels.content.publicEmail }}</dt>
            <dd>
              <a :href="`mailto:${page.public_email}`">{{ page.public_email }}</a>
            </dd>
          </div>
          <div v-if="page.linkedin_url">
            <dt>{{ labels.content.linkedIn }}</dt>
            <dd>
              <a :href="page.linkedin_url" rel="noopener noreferrer">{{ page.linkedin_url }}</a>
            </dd>
          </div>
        </dl>
      </section>

      <section v-if="page.expertise.length" class="authority-detail__expertise">
        <h2>{{ labels.content.expertise }}</h2>
        <ul>
          <li v-for="item in page.expertise" :key="item">{{ item }}</li>
        </ul>
      </section>

      <GeoAnswer :locale="locale" :geo="page.geo" />

      <section v-if="page.authored_knowledge.length" class="authority-detail__articles">
        <h2>{{ labels.content.authoredKnowledge }}</h2>
        <ul>
          <li v-for="article in page.authored_knowledge" :key="article.slug">
            <a :href="article.url">{{ article.name }}</a>
            <p v-if="article.summary">{{ article.summary }}</p>
          </li>
        </ul>
      </section>
    </article>
    <RfqCta :locale="locale" source-type="author_expert" :source-slug="page.slug" />
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

.authority-detail__profile dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.authority-detail__profile dl > div,
.authority-detail__expertise,
.authority-detail__articles li {
  padding: var(--space-5);
  border: var(--border-subtle);
}

.authority-detail__profile dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

.authority-detail__profile dd {
  margin: var(--space-2) 0 0;
}

.authority-detail__expertise ul,
.authority-detail__articles ul {
  margin-block-start: var(--space-4);
}

.authority-detail__articles ul {
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  list-style: none;
}

.authority-detail__articles li p {
  margin-block-start: var(--space-2);
  color: var(--color-neutral-600);
}

@media (max-width: 40rem) {
  .authority-detail__profile dl,
  .authority-detail__articles ul {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
