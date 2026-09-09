<!-- 页面用途：SSR 展示后端已发布 Company Public DTO 中真实存在的公司事实。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type {
  LocaleSlug,
  PublicCardDto,
  PublicCollectionDto,
  PublicCompanyProfileDto,
} from '~/types/public'
import { telephoneHref } from '~/utils/contact'
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
const requestKey = computed(() => `about:${locale.value}`)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicCompanyProfileDto>>(`/public/company-profile/${locale.value}`),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Company profile not found' : 'Company profile unavailable',
  })
}
const page = computed(() => response.value!.data)
const { data: productResponse } = await useAsyncData(`about-products:${locale.value}`, () =>
  api<Envelope<PublicCollectionDto<PublicCardDto>>>(`/public/products/${locale.value}`, {
    query: { page: 1, page_size: 3 },
  }),
)
const aboutProducts = computed(() => productResponse.value?.data.items ?? [])

/** 将已填充 Company DTO 字段映射为本地化事实行，不在模板写任何业务数值。 */
const companyFacts = computed(() =>
  [
    { label: labels.value.home.foundedYear, value: page.value.founded_year },
    { label: labels.value.home.yearsExperience, value: page.value.years_experience },
    { label: labels.value.home.employees, value: page.value.employee_count_range },
    { label: labels.value.home.factoryArea, value: page.value.factory_area_sqm },
    { label: labels.value.home.annualCapacity, value: page.value.annual_capacity_text },
  ].filter((fact) => fact.value !== null && fact.value !== ''),
)
const hasContact = computed(() =>
  Boolean(page.value.phone || page.value.email || page.value.address),
)
// 非号码的演示联系方式保留为可见文字，避免生成不可用的 tel URL。
const phoneHref = computed(() => telephoneHref(page.value.phone))

// canonical、hreflang 与 Schema 全部来自 Company Public DTO。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: page.value.seo.title || page.value.company_name,
  meta: [
    ...(page.value.seo.description
      ? [{ name: 'description', content: page.value.seo.description }]
      : []),
    {
      name: 'robots',
      content: `${page.value.seo.robots_index ? 'index' : 'noindex'}, ${page.value.seo.robots_follow ? 'follow' : 'nofollow'}`,
    },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo.canonical },
    ...page.value.seo.hreflang.map((alternate) => ({
      rel: 'alternate' as const,
      hreflang: alternate.hreflang,
      href: alternate.url,
    })),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>

<template>
  <div class="about-page">
    <div class="public-container about-page__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="labels.navigation.about"
      :title="page.company_name"
      :summary="page.short_intro || page.full_intro || page.company_name"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale })"
      :secondary-label="labels.cta.exploreProducts"
      :secondary-href="`/${locale}/products/`"
    >
      <template #heading
        ><h1>{{ page.company_name }}</h1></template
      >
    </PageHero>

    <article class="public-container about-page__content">
      <section v-if="page.full_intro || page.mission" class="about-page__overview">
        <p class="about-page__section-index">01 / COMPANY PROFILE</p>
        <h2>{{ labels.trust.companyOverview }}</h2>
        <p v-if="page.full_intro">{{ page.full_intro }}</p>
        <p v-if="page.mission">{{ page.mission }}</p>
      </section>

      <section v-if="aboutProducts.length" class="about-page__product-rail">
        <a v-for="(product, index) in aboutProducts" :key="product.slug" :href="product.url">
          <PublicImage
            v-if="product.media?.type === 'image'"
            :media="{ ...product.media, loading: 'lazy' }"
            :locale="locale"
            sizes="(max-width: 40rem) 100vw, 33vw"
          />
          <span>{{ String(index + 1).padStart(2, '0') }}</span>
          <div>
            <strong>{{ product.name }}</strong
            ><small>{{ product.summary }}</small>
          </div>
        </a>
      </section>

      <section v-if="companyFacts.length || page.export_markets?.length" class="about-page__facts">
        <p class="about-page__section-index">02 / VERIFIED DATA</p>
        <h2>{{ labels.trust.companyFacts }}</h2>
        <dl v-if="companyFacts.length">
          <div v-for="fact in companyFacts" :key="fact.label">
            <dt>{{ fact.label }}</dt>
            <dd>{{ fact.value }}</dd>
          </div>
        </dl>
        <div v-if="page.export_markets?.length" class="about-page__market-panel">
          <div>
            <p>DEMO / MARKET DIRECTORY</p>
            <h3>{{ labels.home.exportMarkets }}</h3>
          </div>
          <ul class="about-page__market-grid">
            <li v-for="(market, index) in page.export_markets" :key="market">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <strong>{{ market }}</strong>
            </li>
          </ul>
        </div>
      </section>

      <section v-if="page.advantages?.length" class="about-page__advantages">
        <p class="about-page__section-index">03 / WORKING PRINCIPLES</p>
        <h2>{{ labels.trust.advantages }}</h2>
        <ol class="about-page__advantages-grid">
          <li v-for="(advantage, index) in page.advantages" :key="advantage">
            <span>{{ String(index + 1).padStart(2, '0') }}</span>
            <strong>{{ advantage }}</strong>
          </li>
        </ol>
      </section>

      <GeoAnswer :locale="locale" :geo="page.geo" />

      <section v-if="hasContact" class="about-page__contact">
        <div class="about-page__contact-panel">
          <div>
            <p class="about-page__section-index">04 / CONTACT</p>
            <h2>{{ labels.trust.contact }}</h2>
            <p>{{ labels.home.contactSummary }}</p>
          </div>
          <address>
            <div v-if="page.phone">
              <small>{{ labels.form.phone }}</small>
              <a v-if="phoneHref" :href="phoneHref">{{ page.phone }}</a>
              <span v-else>{{ page.phone }}</span>
            </div>
            <div v-if="page.email">
              <small>{{ labels.form.email }}</small>
              <a :href="`mailto:${page.email}`">{{ page.email }}</a>
            </div>
            <div v-if="page.address">
              <small>{{ locale === 'zh-cn' ? '地址' : 'Address' }}</small>
              <span>{{ page.address }}</span>
            </div>
          </address>
        </div>
      </section>
    </article>
    <RfqCta :locale="locale" />
  </div>
</template>

<style scoped>
.about-page__breadcrumb {
  padding-block: var(--space-4);
}

.about-page__content {
  padding-block: var(--space-12) var(--space-16);
  display: grid;
  gap: clamp(2.5rem, 5vw, 4.25rem);
}

.about-page__overview,
.about-page__facts,
.about-page__advantages,
.about-page__contact {
  display: grid;
  gap: var(--space-4);
}

.about-page__overview p {
  max-width: 54rem;
  color: var(--color-neutral-700);
  line-height: var(--line-height-relaxed);
  white-space: pre-line;
}
.about-page__overview {
  position: relative;
  padding: clamp(1.5rem, 4vw, 3rem);
  color: #dcebf7;
  background:
    linear-gradient(120deg, rgb(3 20 38 / 98%), rgb(7 69 119 / 92%)), var(--color-navy-900);
  border-left: 4px solid #2ca6ee;
}
.about-page__overview h2 {
  max-width: 18ch;
  color: #fff;
  font-size: clamp(1.8rem, 4vw, 3.2rem);
}
.about-page__overview p:not(.about-page__section-index) {
  color: #c6daea;
}
.about-page__section-index {
  margin: 0;
  color: #278fd0;
  font-family: var(--font-technical);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.about-page__overview .about-page__section-index {
  color: #7cccf6;
}
.about-page__product-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  background: #c8d8e5;
  border: 1px solid #c8d8e5;
}
.about-page__product-rail a {
  min-width: 0;
  padding-bottom: 1rem;
  display: grid;
  grid-template-columns: 2.2rem minmax(0, 1fr);
  gap: 0.8rem;
  color: #143653;
  background: #fff;
  text-decoration: none;
}
.about-page__product-rail :deep(.public-image) {
  grid-column: 1 / -1;
}
.about-page__product-rail :deep(img) {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
}
.about-page__product-rail > a > span {
  padding-left: 1rem;
  color: #1882c9;
  font-family: var(--font-technical);
  font-size: 0.7rem;
  font-weight: 800;
}
.about-page__product-rail strong,
.about-page__product-rail small {
  display: block;
}
.about-page__product-rail small {
  margin-top: 0.3rem;
  padding-right: 1rem;
  color: #687c8d;
  font-size: 0.75rem;
  line-height: 1.5;
}

.about-page__facts dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.about-page__facts dl > div {
  padding: var(--space-5);
  background: #f3f8fb;
  border-top: 3px solid #278fd0;
}

.about-page__facts dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

.about-page__facts dd {
  margin: var(--space-2) 0 0;
  color: var(--color-navy-900);
  font-weight: 750;
}

.about-page__market-panel {
  padding: clamp(1.4rem, 3vw, 2.4rem);
  display: grid;
  grid-template-columns: minmax(12rem, 0.7fr) minmax(0, 1.6fr);
  gap: clamp(1.5rem, 4vw, 4rem);
  color: #e2eff8;
  background:
    linear-gradient(125deg, rgb(3 27 51 / 98%), rgb(5 65 108 / 93%)), var(--color-navy-900);
}

.about-page__market-panel > div > p {
  margin: 0;
  color: #6fc5f4;
  font-family: var(--font-technical);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.about-page__market-panel h3 {
  margin-top: 0.55rem;
  color: #fff;
  font-size: clamp(1.45rem, 3vw, 2.4rem);
}

.about-page__market-grid,
.about-page__advantages-grid {
  margin: 0;
  padding: 0;
  list-style: none;
}

.about-page__market-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid rgb(135 196 232 / 28%);
  border-left: 1px solid rgb(135 196 232 / 28%);
}

.about-page__market-grid li {
  min-height: 5.2rem;
  padding: 1rem;
  display: grid;
  align-content: space-between;
  gap: 0.8rem;
  border-right: 1px solid rgb(135 196 232 / 28%);
  border-bottom: 1px solid rgb(135 196 232 / 28%);
}

.about-page__market-grid span,
.about-page__advantages-grid span {
  color: #2da5e9;
  font-family: var(--font-technical);
  font-size: 0.68rem;
  font-weight: 800;
}

.about-page__advantages-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  background: #cbdce8;
  border: 1px solid #cbdce8;
}

.about-page__advantages-grid li {
  min-height: 9rem;
  padding: clamp(1.2rem, 2.5vw, 2rem);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 2rem;
  color: #102f4a;
  background: #f7fafc;
}

.about-page__advantages-grid strong {
  font-size: clamp(1.05rem, 2vw, 1.4rem);
  line-height: 1.35;
}

.about-page__contact-panel {
  padding: clamp(1.5rem, 4vw, 3rem);
  display: grid;
  grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
  gap: clamp(2rem, 5vw, 5rem);
  color: #d4e4ef;
  background: #071f36;
  border-bottom: 4px solid #158bd1;
}

.about-page__contact-panel h2 {
  margin-top: 0.6rem;
  color: #fff;
  font-size: clamp(1.6rem, 3vw, 2.6rem);
}

.about-page__contact-panel > div > p:last-child {
  margin-top: 1rem;
  color: #a9c1d2;
  line-height: 1.65;
}

.about-page__contact address {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  font-style: normal;
  background: rgb(163 202 227 / 22%);
  border: 1px solid rgb(163 202 227 / 22%);
}

.about-page__contact address > div {
  min-width: 0;
  padding: 1rem 1.1rem;
  display: grid;
  align-content: center;
  gap: 0.45rem;
  background: rgb(9 48 79 / 94%);
}

.about-page__contact address > div:last-child:nth-child(odd) {
  grid-column: 1 / -1;
}

.about-page__contact small {
  color: #78bfe8;
  font-family: var(--font-technical);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.about-page__contact a,
.about-page__contact span {
  overflow-wrap: anywhere;
  color: #fff;
  font-weight: 700;
}

@media (max-width: 48rem) {
  .about-page__facts dl,
  .about-page__product-rail {
    grid-template-columns: minmax(0, 1fr);
  }

  .about-page__market-panel,
  .about-page__contact-panel {
    grid-template-columns: minmax(0, 1fr);
  }

  .about-page__advantages-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 34rem) {
  .about-page__market-grid,
  .about-page__contact address {
    grid-template-columns: minmax(0, 1fr);
  }

  .about-page__contact address > div:last-child:nth-child(odd) {
    grid-column: auto;
  }
}
</style>
