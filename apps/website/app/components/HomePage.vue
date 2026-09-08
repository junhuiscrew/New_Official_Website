<!-- 组件职责：按已确认顺序组合单次 Public Home DTO，不在前端判断或制造发布事实。 -->
<script setup lang="ts">
import { computed } from 'vue'

import ArticleCard from './ArticleCard.vue'
import CaseCard from './CaseCard.vue'
import HomepagePresentation from './HomepagePresentation.vue'
import PageHero from './PageHero.vue'
import ProductCard from './ProductCard.vue'
import RfqCta from './RfqCta.vue'
import SectionHeader from './SectionHeader.vue'
import TrustMetric from './TrustMetric.vue'
import { ui } from '~/i18n/ui'
import type { HomeDto, LocaleSlug, PublicCardDto } from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'

const props = defineProps<{ locale: LocaleSlug; home: HomeDto; preview?: boolean }>()
const labels = computed(() => ui[props.locale])
const heroTitle = computed(
  () => props.home.company?.company_name?.trim() || labels.value.home.fallbackTitle,
)
const heroSummary = computed(
  () =>
    props.home.company?.short_intro?.trim() ||
    props.home.company?.mission?.trim() ||
    labels.value.home.fallbackSummary,
)
const advantages = computed(() =>
  (props.home.company?.advantages ?? []).filter((item) => Boolean(item.trim())),
)

interface HomeMetric {
  key: string
  label: string
  value: string
}

/**
 * 将后端显式返回的 Trust Summary 字段转成展示项。
 *
 * 输入：无，直接读取 props.home.trust_summary。
 * 输出：HomeMetric[]，仅包含非空公开事实，不计算或补造数值。
 */
const trustMetrics = computed<HomeMetric[]>(() => {
  const trust = props.home.trust_summary
  if (!trust) return []

  const metrics: Array<HomeMetric | null> = [
    trust.founded_year !== undefined
      ? {
          key: 'founded-year',
          label: labels.value.home.foundedYear,
          value: String(trust.founded_year),
        }
      : null,
    trust.years_experience !== undefined
      ? {
          key: 'years-experience',
          label: labels.value.home.yearsExperience,
          value: String(trust.years_experience),
        }
      : null,
    trust.employee_count_range?.trim()
      ? {
          key: 'employees',
          label: labels.value.home.employees,
          value: trust.employee_count_range,
        }
      : null,
    trust.factory_area_sqm !== undefined
      ? {
          key: 'factory-area',
          label: labels.value.home.factoryArea,
          value: String(trust.factory_area_sqm),
        }
      : null,
    trust.annual_capacity_text?.trim()
      ? {
          key: 'annual-capacity',
          label: labels.value.home.annualCapacity,
          value: trust.annual_capacity_text,
        }
      : null,
    trust.export_markets?.length
      ? {
          key: 'export-markets',
          label: labels.value.home.exportMarkets,
          value: trust.export_markets.join(' · '),
        }
      : null,
  ]
  return metrics.filter((metric): metric is HomeMetric => metric !== null)
})

/** 仅将后端可选 SEO 与 Schema 放入 Head；API 未提供时不生成替代规则。 */
useHead(() => {
  const seo = props.home.seo
  const heroPreload =
    props.home.hero_media?.type === 'image'
      ? [
          {
            rel: 'preload',
            as: 'image',
            href: props.home.hero_media.src,
            fetchpriority: 'high',
          },
        ]
      : []
  const head: Record<string, unknown> = {
    htmlAttrs: { lang: props.locale === 'zh-cn' ? 'zh-CN' : 'en' },
    // 空数据环境仍提供与可见 H1 一致的页面标题，避免浏览器标签和辅助技术名称为空。
    title: heroTitle.value,
    ...(heroPreload.length ? { link: heroPreload } : {}),
  }

  if (seo) {
    head.title = seo.title
    head.meta = [
      ...(seo.description ? [{ name: 'description', content: seo.description }] : []),
      // 认证完整预览必须覆盖公开 SEO 的索引资格，避免 Head 合并时回退为 index。
      { name: 'robots', content: props.preview ? 'noindex, nofollow' : seo.robots },
      ...(seo.og_title ? [{ property: 'og:title', content: seo.og_title }] : []),
      ...(seo.og_description ? [{ property: 'og:description', content: seo.og_description }] : []),
    ]
    head.link = [
      ...heroPreload,
      { rel: 'canonical', href: seo.canonical },
      ...Object.entries(seo.hreflang ?? {}).map(([hreflang, href]) => ({
        rel: 'alternate',
        hreflang,
        href,
      })),
    ]
  }

  if (props.home.schema !== undefined && props.home.schema !== null) {
    head.script = [
      {
        type: 'application/ld+json',
        innerHTML: serializeJsonLd(props.home.schema),
      },
    ]
  }
  return head
})

/** 首页通用内容卡仅消费 canonical Public Card DTO，不拼接详情 URL。 */
function cardKey(item: PublicCardDto): string {
  return `${item.type}:${item.url}`
}
</script>

<template>
  <div class="home-page">
    <HomepagePresentation
      v-if="home.presentation"
      :locale="locale"
      :home="home"
      :preview="preview ?? home.preview ?? false"
    />

    <template v-else>
      <PageHero
        :title="heroTitle"
        :summary="heroSummary"
        :primary-label="labels.cta.requestQuote"
        :primary-href="`/${locale}/request-a-quote/`"
        :secondary-label="labels.cta.exploreProducts"
        :secondary-href="`/${locale}/products/`"
        :media="home.hero_media"
      />

      <section
        v-if="home.product_categories.length"
        class="public-section"
        data-home-section="product-categories"
      >
        <div class="public-container">
          <SectionHeader
            :title="labels.sections.productCategories"
            :description="labels.home.categoriesIntro"
          />
          <div class="home-grid home-grid--categories">
            <article
              v-for="item in home.product_categories"
              :key="cardKey(item)"
              class="home-link-card"
            >
              <img
                v-if="item.media?.type === 'image'"
                data-testid="card-media"
                :src="item.media.src"
                :alt="item.media.alt"
                :width="item.media.width ?? undefined"
                :height="item.media.height ?? undefined"
                loading="lazy"
              />
              <div>
                <h3>
                  <a :href="item.url">{{ item.name }}</a>
                </h3>
                <p v-if="item.summary">{{ item.summary }}</p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section
        v-if="advantages.length"
        class="home-trust-strip"
        data-home-section="trust-strip"
        :aria-labelledby="`trust-strip-title-${locale}`"
      >
        <div class="public-container">
          <h2 :id="`trust-strip-title-${locale}`">{{ labels.sections.whyJunhui }}</h2>
          <ul>
            <li v-for="advantage in advantages" :key="advantage">{{ advantage }}</li>
          </ul>
        </div>
      </section>

      <section
        v-if="home.materials.length || home.solutions.length"
        class="public-section public-section--muted"
        data-home-section="discovery"
      >
        <div class="public-container">
          <SectionHeader :title="labels.home.discoveryTitle" />
          <div class="home-discovery">
            <section v-if="home.materials.length">
              <h3>{{ labels.sections.solveByMaterial }}</h3>
              <ul class="home-link-list">
                <li v-for="item in home.materials" :key="cardKey(item)">
                  <a :href="item.url">
                    <span>{{ item.name }}</span>
                    <small v-if="item.summary">{{ item.summary }}</small>
                  </a>
                </li>
              </ul>
            </section>
            <section v-if="home.solutions.length">
              <h3>{{ labels.sections.solveByProblem }}</h3>
              <ul class="home-link-list">
                <li v-for="item in home.solutions" :key="cardKey(item)">
                  <a :href="item.url">
                    <span>{{ item.name }}</span>
                    <small v-if="item.summary">{{ item.summary }}</small>
                  </a>
                </li>
              </ul>
            </section>
          </div>
        </div>
      </section>

      <section
        v-if="home.capabilities.length"
        class="public-section"
        data-home-section="capabilities"
      >
        <div class="public-container">
          <SectionHeader
            :title="labels.sections.manufacturingCapabilities"
            :description="labels.home.capabilitiesIntro"
          />
          <div class="home-grid">
            <article v-for="item in home.capabilities" :key="cardKey(item)" class="home-text-card">
              <p class="eyebrow">{{ labels.navigation.capabilities }}</p>
              <h3>
                <a :href="item.url">{{ item.name }}</a>
              </h3>
              <p v-if="item.summary">{{ item.summary }}</p>
            </article>
          </div>
        </div>
      </section>

      <section
        v-if="home.featured_products.length"
        class="public-section public-section--muted"
        data-home-section="featured-products"
      >
        <div class="public-container">
          <SectionHeader
            :title="labels.sections.featuredProducts"
            :description="labels.home.productsIntro"
          />
          <div class="home-grid">
            <ProductCard
              v-for="item in home.featured_products"
              :key="cardKey(item)"
              :item="item"
              :locale="locale"
            />
          </div>
        </div>
      </section>

      <section
        v-if="home.applications.length"
        class="public-section"
        data-home-section="applications"
      >
        <div class="public-container">
          <SectionHeader
            :title="labels.sections.applications"
            :description="labels.home.applicationsIntro"
          />
          <div class="home-grid">
            <article v-for="item in home.applications" :key="cardKey(item)" class="home-link-card">
              <img
                v-if="item.media?.type === 'image'"
                data-testid="card-media"
                :src="item.media.src"
                :alt="item.media.alt"
                :width="item.media.width ?? undefined"
                :height="item.media.height ?? undefined"
                loading="lazy"
              />
              <div>
                <h3>
                  <a :href="item.url">{{ item.name }}</a>
                </h3>
                <p v-if="item.summary">{{ item.summary }}</p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section
        v-if="home.cases.length"
        class="public-section public-section--muted"
        data-home-section="cases"
      >
        <div class="public-container">
          <SectionHeader
            :title="labels.sections.caseStudies"
            :description="labels.home.casesIntro"
          />
          <div class="home-grid home-grid--wide">
            <CaseCard
              v-for="item in home.cases"
              :key="cardKey(item)"
              :item="item"
              :locale="locale"
            />
          </div>
        </div>
      </section>

      <section v-if="home.knowledge.length" class="public-section" data-home-section="knowledge">
        <div class="public-container">
          <SectionHeader
            :title="labels.sections.technicalKnowledge"
            :description="labels.home.knowledgeIntro"
          />
          <div class="home-grid">
            <ArticleCard
              v-for="item in home.knowledge"
              :key="cardKey(item)"
              :item="item"
              :locale="locale"
            />
          </div>
        </div>
      </section>

      <section
        v-if="trustMetrics.length"
        class="public-section public-section--muted"
        data-home-section="trust-summary"
      >
        <div class="public-container">
          <SectionHeader :title="labels.home.trustTitle" :description="labels.home.trustIntro" />
          <dl class="home-metrics">
            <TrustMetric
              v-for="metric in trustMetrics"
              :key="metric.key"
              :label="metric.label"
              :value="metric.value"
            />
          </dl>
        </div>
      </section>

      <RfqCta :locale="locale" />
    </template>
  </div>
</template>

<style scoped>
.home-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}

.home-grid--categories {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.home-grid--wide {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.home-link-card,
.home-text-card {
  min-width: 0;
  background: var(--color-white);
  border: var(--border-subtle);
}

.home-link-card > img {
  width: 100%;
  aspect-ratio: 3 / 2;
  object-fit: cover;
}

.home-link-card > div,
.home-text-card {
  padding: var(--space-5);
  display: grid;
  gap: var(--space-3);
}

.home-link-card h3 a,
.home-text-card h3 a {
  color: var(--color-navy-900);
  text-decoration: none;
}

.home-link-card p,
.home-text-card > p:last-child {
  color: var(--color-neutral-600);
}

.home-trust-strip {
  padding-block: var(--space-8);
  color: var(--color-white);
  background: var(--color-blue-700);
}

.home-trust-strip > div {
  display: grid;
  grid-template-columns: minmax(12rem, 0.35fr) minmax(0, 1fr);
  align-items: center;
  gap: var(--space-8);
}

.home-trust-strip h2 {
  color: var(--color-white);
  font-size: var(--font-size-h3);
}

.home-trust-strip ul {
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: var(--space-4);
  list-style: none;
}

.home-trust-strip li {
  padding-inline-start: var(--space-4);
  border-inline-start: 2px solid var(--color-blue-100);
}

.home-discovery {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-10);
}

.home-discovery section {
  display: grid;
  align-content: start;
  gap: var(--space-5);
}

.home-link-list {
  margin: 0;
  padding: 0;
  display: grid;
  list-style: none;
  border-block-start: var(--border-strong);
}

.home-link-list li {
  border-block-end: var(--border-strong);
}

.home-link-list a {
  padding-block: var(--space-4);
  display: grid;
  gap: var(--space-1);
  color: var(--color-navy-900);
  text-decoration: none;
}

.home-link-list span {
  font-weight: 750;
}

.home-link-list small {
  color: var(--color-neutral-600);
}

.home-metrics {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--space-8);
}

@media (max-width: 64rem) {
  .home-grid,
  .home-grid--categories {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 40rem) {
  .home-grid,
  .home-grid--categories,
  .home-grid--wide,
  .home-discovery,
  .home-trust-strip > div {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
