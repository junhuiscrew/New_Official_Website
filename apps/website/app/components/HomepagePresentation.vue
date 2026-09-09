<!-- 组件职责：按服务端首页配置渲染普通首页和认证完整布局预览，共享同一组十四模块。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type {
  HomeDto,
  HomepageModuleDto,
  HomepageModuleKey,
  LocaleSlug,
  PublicCardDto,
} from '~/types/public'

import PublicImage from './PublicImage.vue'
import PublicVideo from './PublicVideo.vue'

const props = defineProps<{ locale: LocaleSlug; home: HomeDto; preview: boolean }>()
const labels = computed(() => ui[props.locale])

/** 公开首页只显示有内容且启用的模块；认证预览保留全部十四个位置。 */
const renderedModules = computed(() =>
  (props.home.presentation?.modules ?? []).filter(
    (module) => props.preview || (module.visible && module.content_status === 'available'),
  ),
)

const heroTitle = computed(
  () =>
    (props.home.demo_mode ? props.home.company?.mission?.trim() : '') ||
    props.home.company?.company_name?.trim() ||
    labels.value.home.fallbackTitle,
)
const heroSummary = computed(
  () => props.home.company?.short_intro?.trim() || labels.value.home.fallbackSummary,
)
const aboutParagraphs = computed(() => {
  const source =
    props.home.company?.full_intro?.trim() || props.home.company?.short_intro?.trim() || ''
  return source
    .split(/\n+/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
})
const companyFactChips = computed(() =>
  [
    { label: labels.value.home.foundedYear, value: props.home.company?.founded_year },
    { label: labels.value.home.yearsExperience, value: props.home.company?.years_experience },
    { label: labels.value.home.employees, value: props.home.company?.employee_count_range },
    { label: labels.value.home.factoryArea, value: props.home.company?.factory_area_sqm },
  ].filter((fact) => fact.value !== null && fact.value !== undefined && fact.value !== ''),
)
const companyAdvantages = computed(() =>
  (props.home.company?.advantages ?? []).map((item) => item.trim()).filter(Boolean),
)

/** 输入固定模块键；输出当前语言的纯界面标题。 */
function moduleTitle(key: HomepageModuleKey): string {
  return labels.value.presentation.moduleNames[key]
}

/** 输入站内路径；输出预览和普通站均能正确点击的本地域名地址。 */
function publicHref(path: string | null | undefined): string {
  if (!path) return '#'
  return path
}

/** 输入管理路径；输出只在 Admin 域名内打开的真实入口。 */
function adminHref(path: string): string {
  const origin = props.home.demo_mode
    ? 'https://admin-demo.junhuiscrewbarrel.com'
    : 'https://admin.junhuiscrewbarrel.com'
  return `${origin}${path}`
}

/** 按模块声明的 slug 顺序筛选后端已核验产品，不制造 featured 关系。 */
function productsFor(module: HomepageModuleDto): PublicCardDto[] {
  const products = props.home.homepage_products ?? []
  if (!module.product_slugs.length) return products
  const bySlug = new Map(products.map((product) => [product.slug, product]))
  return module.product_slugs
    .map((slug) => bySlug.get(slug))
    .filter((product): product is PublicCardDto => Boolean(product))
}

/** 返回通用内容模块已经通过公开门禁的卡片。 */
function cardsFor(key: HomepageModuleKey): PublicCardDto[] {
  const sources: Partial<Record<HomepageModuleKey, PublicCardDto[] | undefined>> = {
    materials: props.home.materials,
    special_applications: props.home.applications,
    technologies: props.home.technologies,
    manufacturing_capability: props.home.capabilities,
    solutions: props.home.solutions,
    case_studies: props.home.cases,
    technical_knowledge: props.home.knowledge,
  }
  return sources[key] ?? []
}
</script>

<template>
  <div class="presentation-home" :class="{ 'presentation-home--preview': preview }">
    <aside v-if="preview" class="preview-notice" aria-label="Preview status">
      <strong>{{ labels.presentation.previewBadge }}</strong>
      <span>{{ labels.presentation.previewNotice }}</span>
    </aside>

    <template v-for="(module, moduleIndex) in renderedModules" :key="module.key">
      <section
        v-if="module.key === 'hero'"
        class="presentation-hero"
        :class="`presentation-module--${module.variant}`"
        data-home-module="hero"
      >
        <div class="presentation-hero__glow" aria-hidden="true" />
        <div class="public-container presentation-hero__grid">
          <div class="presentation-hero__copy">
            <div class="presentation-hero__badges">
              <p class="presentation-kicker">{{ labels.presentation.badge }}</p>
              <span v-if="home.demo_mode" class="presentation-demo-badge">DEMO R2</span>
            </div>
            <h1>{{ heroTitle }}</h1>
            <p class="presentation-hero__summary">{{ heroSummary }}</p>
            <p v-if="home.demo_mode" class="presentation-hero__company">
              {{ home.company?.company_name }}
            </p>
            <div class="presentation-actions">
              <a class="button button--primary" :href="publicHref(`/${locale}/products/`)">
                {{ labels.cta.exploreProducts }}
              </a>
              <a class="button button--ghost" :href="publicHref(`/${locale}/request-a-quote/`)">
                {{ labels.cta.requestQuote }}
              </a>
            </div>
          </div>
          <div v-if="home.hero_media?.type === 'image'" class="presentation-hero__visual">
            <figure class="presentation-hero__main-media">
              <PublicImage
                :media="{ ...home.hero_media, loading: 'eager' }"
                :locale="locale"
                sizes="(max-width: 48rem) 100vw, 48vw"
              />
            </figure>
            <div v-if="productsFor(module).length" class="presentation-hero__product-tags">
              <a
                v-for="(product, productIndex) in productsFor(module).slice(0, 3)"
                :key="product.slug"
                :href="publicHref(product.url)"
              >
                <span>{{ String(productIndex + 1).padStart(2, '0') }}</span>
                {{ product.name }}
              </a>
            </div>
          </div>
          <div
            v-else-if="productsFor(module).length"
            class="presentation-hero__visual"
            aria-hidden="true"
          >
            <figure v-for="product in productsFor(module).slice(0, 3)" :key="product.slug">
              <PublicImage
                v-if="product.media?.type === 'image'"
                :media="{ ...product.media, loading: moduleIndex === 0 ? 'eager' : 'lazy' }"
                :locale="locale"
                sizes="(max-width: 40rem) 46vw, 24vw"
              />
            </figure>
          </div>
          <div
            v-else-if="preview && module.content_status === 'missing'"
            class="presentation-empty presentation-empty--dark"
            data-testid="homepage-module-empty"
          >
            <p>{{ module.missing_reason || labels.presentation.contentUnavailable }}</p>
            <a :href="adminHref(module.management_url)">{{ labels.presentation.manage }}</a>
          </div>
        </div>
      </section>

      <section
        v-else-if="module.key === 'rfq_cta'"
        class="presentation-rfq"
        :class="`presentation-module--${module.variant}`"
        data-home-module="rfq_cta"
      >
        <div class="public-container presentation-rfq__inner">
          <div>
            <p class="presentation-kicker">{{ moduleTitle(module.key) }}</p>
            <h2>{{ labels.home.rfqTitle }}</h2>
            <p>{{ labels.home.rfqSummary }}</p>
          </div>
          <a class="button button--primary" :href="publicHref(`/${locale}/request-a-quote/`)">
            {{ labels.cta.requestQuote }}
          </a>
        </div>
      </section>

      <section
        v-else
        class="presentation-section"
        :class="[`presentation-module--${module.variant}`, `presentation-section--${module.key}`]"
        :data-home-module="module.key"
      >
        <div class="public-container presentation-section__inner">
          <header class="presentation-heading">
            <p class="presentation-index">{{ String(moduleIndex + 1).padStart(2, '0') }}</p>
            <div>
              <p class="presentation-kicker">{{ labels.presentation.badge }}</p>
              <h2>{{ moduleTitle(module.key) }}</h2>
            </div>
          </header>

          <div
            v-if="module.content_status === 'missing'"
            class="presentation-empty"
            data-testid="homepage-module-empty"
          >
            <span aria-hidden="true">＋</span>
            <p>{{ module.missing_reason || labels.presentation.contentUnavailable }}</p>
            <a :href="adminHref(module.management_url)">{{ labels.presentation.manage }}</a>
          </div>

          <div v-else-if="module.key === 'core_product_families'" class="presentation-core">
            <div v-if="home.product_categories.length" class="presentation-category-rail">
              <a
                v-for="category in home.product_categories"
                :key="category.slug"
                :href="publicHref(category.url)"
              >
                <span>{{ category.name }}</span>
                <small v-if="category.summary">{{ category.summary }}</small>
              </a>
            </div>
            <div class="presentation-products">
              <article
                v-for="product in productsFor(module)"
                :key="product.slug"
                data-testid="homepage-product-card"
              >
                <a :href="publicHref(product.url)" class="presentation-products__image">
                  <PublicImage
                    v-if="product.media?.type === 'image'"
                    :media="{ ...product.media, loading: 'lazy' }"
                    :locale="locale"
                    sizes="(max-width: 40rem) 100vw, 33vw"
                  />
                </a>
                <div>
                  <p v-if="product.category" class="eyebrow">{{ product.category.name }}</p>
                  <h3>
                    <a :href="publicHref(product.url)">{{ product.name }}</a>
                  </h3>
                  <p v-if="product.summary">{{ product.summary }}</p>
                  <a class="presentation-text-link" :href="publicHref(product.url)">
                    {{ labels.cta.viewDetails }} <span aria-hidden="true">→</span>
                  </a>
                </div>
              </article>
            </div>
          </div>

          <div v-else-if="module.key === 'materials'" class="presentation-materials">
            <a
              v-for="(item, itemIndex) in cardsFor(module.key)"
              :key="`${item.type}:${item.slug}`"
              :href="publicHref(item.url)"
            >
              <span>{{ String(itemIndex + 1).padStart(2, '0') }}</span>
              <PublicImage
                v-if="item.media?.type === 'image'"
                :media="{ ...item.media, loading: 'lazy' }"
                :locale="locale"
                sizes="(max-width: 40rem) 44vw, 18vw"
              />
              <div>
                <h3>{{ item.name }}</h3>
                <p v-if="item.summary">{{ item.summary }}</p>
              </div>
            </a>
          </div>

          <div v-else-if="module.key === 'special_applications'" class="presentation-applications">
            <a
              v-if="cardsFor(module.key)[0]"
              class="presentation-applications__feature"
              :class="{
                'presentation-applications__feature--text-only':
                  cardsFor(module.key)[0]!.media?.type !== 'image',
              }"
              :href="publicHref(cardsFor(module.key)[0]!.url)"
            >
              <PublicImage
                v-if="cardsFor(module.key)[0]!.media?.type === 'image'"
                :media="{ ...cardsFor(module.key)[0]!.media!, loading: 'lazy' }"
                :locale="locale"
                sizes="(max-width: 48rem) 100vw, 58vw"
              />
              <div>
                <p class="eyebrow">01 / FEATURED DEMO APPLICATION</p>
                <h3>{{ cardsFor(module.key)[0]!.name }}</h3>
                <p>{{ cardsFor(module.key)[0]!.summary }}</p>
              </div>
            </a>
            <div class="presentation-applications__list">
              <a
                v-for="(item, itemIndex) in cardsFor(module.key).slice(1)"
                :key="`${item.type}:${item.slug}`"
                :href="publicHref(item.url)"
              >
                <span>{{ String(itemIndex + 2).padStart(2, '0') }}</span>
                <div>
                  <h3>{{ item.name }}</h3>
                  <p v-if="item.summary">{{ item.summary }}</p>
                </div>
                <b aria-hidden="true">→</b>
              </a>
            </div>
          </div>

          <ol v-else-if="module.key === 'technologies'" class="presentation-technologies">
            <li
              v-for="(item, itemIndex) in cardsFor(module.key)"
              :key="`${item.type}:${item.slug}`"
            >
              <a :href="publicHref(item.url)">
                <span>{{ String(itemIndex + 1).padStart(2, '0') }}</span>
                <div>
                  <h3>{{ item.name }}</h3>
                  <p v-if="item.summary">{{ item.summary }}</p>
                </div>
              </a>
            </li>
          </ol>

          <div v-else-if="module.key === 'why_junhui'" class="presentation-about">
            <div class="presentation-about__marker" aria-hidden="true">JH</div>
            <div>
              <p v-for="paragraph in aboutParagraphs" :key="paragraph">{{ paragraph }}</p>
              <ol v-if="companyAdvantages.length" class="presentation-about__advantages">
                <li v-for="(advantage, advantageIndex) in companyAdvantages" :key="advantage">
                  <span>{{ String(advantageIndex + 1).padStart(2, '0') }}</span>
                  <strong>{{ advantage }}</strong>
                </li>
              </ol>
              <dl v-if="companyFactChips.length" class="presentation-about__facts">
                <div v-for="fact in companyFactChips" :key="fact.label">
                  <dt>{{ fact.label }}</dt>
                  <dd>{{ fact.value }}</dd>
                </div>
              </dl>
              <a class="presentation-text-link" :href="publicHref(`/${locale}/about/`)">
                {{ labels.navigation.about }} <span aria-hidden="true">→</span>
              </a>
            </div>
          </div>

          <div v-else-if="module.key === 'factory_equipment'" class="presentation-factory">
            <div v-if="home.demo_videos?.length" class="presentation-video-grid">
              <article v-for="(video, videoIndex) in home.demo_videos" :key="video.media.src">
                <div>
                  <p class="eyebrow">DEMO VIDEO {{ String(videoIndex + 1).padStart(2, '0') }}</p>
                  <h3>{{ video.media.alt }}</h3>
                </div>
                <PublicVideo :media="video.media" :poster="video.poster" />
              </article>
            </div>
            <div class="presentation-equipment-rail">
              <article v-for="equipment in home.equipment ?? []" :key="equipment.slug">
                <p class="eyebrow">{{ equipment.type }}</p>
                <h3>{{ equipment.title }}</h3>
                <p v-if="equipment.summary">{{ equipment.summary }}</p>
              </article>
            </div>
          </div>

          <div v-else-if="module.key === 'certificates_patents'" class="presentation-data-grid">
            <article
              v-for="record in [...(home.certificates ?? []), ...(home.patents ?? [])]"
              :key="`${record.type}:${record.slug}`"
            >
              <p class="eyebrow">{{ record.type }}</p>
              <h3>
                <a v-if="record.url" :href="publicHref(record.url)">{{ record.title }}</a>
                <template v-else>{{ record.title }}</template>
              </h3>
              <p v-if="record.summary">{{ record.summary }}</p>
            </article>
          </div>

          <ul v-else-if="module.key === 'global_markets'" class="presentation-markets">
            <li v-for="market in home.company?.export_markets ?? []" :key="market">{{ market }}</li>
            <li v-if="home.demo_mode" class="presentation-markets__note">
              {{ labels.presentation.marketDisclaimer }}
            </li>
          </ul>

          <div v-else class="presentation-data-grid">
            <article v-for="item in cardsFor(module.key)" :key="`${item.type}:${item.slug}`">
              <PublicImage
                v-if="item.media?.type === 'image'"
                :media="{ ...item.media, loading: 'lazy' }"
                :locale="locale"
                sizes="(max-width: 40rem) 100vw, 33vw"
              />
              <p class="eyebrow">{{ moduleTitle(module.key) }}</p>
              <h3>
                <a :href="publicHref(item.url)">{{ item.name }}</a>
              </h3>
              <p v-if="item.summary">{{ item.summary }}</p>
            </article>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.presentation-home {
  --presentation-line: rgb(138 184 229 / 26%);
  overflow: clip;
  background: #fff;
}

.preview-notice {
  position: sticky;
  z-index: 20;
  top: 0;
  padding: 0.7rem var(--container-gutter);
  display: flex;
  justify-content: center;
  gap: var(--space-4);
  color: #072544;
  background: #dff1ff;
  border-bottom: 1px solid #b6dcfa;
  font-size: var(--font-size-small);
}

.presentation-hero {
  position: relative;
  isolation: isolate;
  min-height: min(46rem, calc(100svh - 5rem));
  display: grid;
  align-items: center;
  overflow: hidden;
  color: var(--color-white);
  background: linear-gradient(
    105deg,
    rgb(3 17 35 / 98%) 0%,
    rgb(6 39 75 / 96%) 52%,
    rgb(8 79 158 / 88%) 100%
  );
}

.presentation-hero::before {
  position: absolute;
  z-index: -1;
  inset: 0;
  background-image:
    linear-gradient(var(--presentation-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--presentation-line) 1px, transparent 1px);
  background-size: 5rem 5rem;
  content: '';
  mask-image: linear-gradient(90deg, transparent, #000 55%, #000);
}

.presentation-hero__glow {
  position: absolute;
  z-index: -1;
  width: 42rem;
  height: 42rem;
  right: -10rem;
  bottom: -20rem;
  background: rgb(31 151 255 / 32%);
  border-radius: 50%;
  filter: blur(70px);
}

.presentation-hero__grid {
  padding-block: clamp(5rem, 10vw, 8rem);
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(20rem, 0.95fr);
  align-items: center;
  gap: clamp(3rem, 7vw, 7rem);
}

.presentation-hero__copy {
  display: grid;
  gap: var(--space-6);
}

.presentation-hero__badges {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.presentation-hero__badges .presentation-kicker {
  margin: 0;
}

.presentation-demo-badge {
  padding: 0.34rem 0.55rem;
  color: #082a4f;
  background: #8fd2ff;
  border-radius: 99rem;
  font-family: var(--font-technical);
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.11em;
}

.presentation-kicker,
.presentation-index {
  color: #75bdff;
  font-family: var(--font-technical);
  font-size: var(--font-size-label);
  font-weight: 700;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.presentation-hero h1 {
  max-width: 14ch;
  color: var(--color-white);
  font-size: clamp(2.55rem, 5.5vw, 5.4rem);
}

.presentation-hero__summary {
  max-width: 43rem;
  color: #d6e7f7;
  font-size: clamp(1rem, 1.5vw, 1.2rem);
}

.presentation-hero__company {
  color: #8fc8f6;
  font-family: var(--font-technical);
  font-size: var(--font-size-small);
  letter-spacing: 0.04em;
}

.presentation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.button {
  min-height: 3.15rem;
  padding: 0.75rem 1.4rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-white);
  font-weight: 750;
  text-decoration: none;
  border: 1px solid transparent;
}

.button--primary {
  background: var(--color-blue-600);
}

.button--ghost {
  background: rgb(255 255 255 / 4%);
  border-color: rgb(255 255 255 / 42%);
}

.presentation-hero__visual {
  position: relative;
  min-height: 31rem;
}

.presentation-hero__visual:has(.presentation-hero__main-media) {
  min-height: auto;
}

.presentation-hero__visual > figure {
  position: absolute;
  margin: 0;
  width: min(20rem, 68%);
  overflow: hidden;
  background: #edf6ff;
  border: 1px solid rgb(255 255 255 / 26%);
  box-shadow: 0 2rem 5rem rgb(0 9 22 / 42%);
}

.presentation-hero__visual > figure:nth-child(1) {
  top: 0;
  right: 0;
}

.presentation-hero__visual > figure:nth-child(2) {
  top: 9rem;
  left: 0;
}

.presentation-hero__visual > figure:nth-child(3) {
  right: 2rem;
  bottom: 0;
}

.presentation-hero__visual :deep(img) {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
}

.presentation-hero__visual > .presentation-hero__main-media {
  position: relative;
  inset: auto;
  width: 100%;
  border: 1px solid rgb(255 255 255 / 24%);
  box-shadow: 0 2.4rem 6rem rgb(0 9 22 / 50%);
}

.presentation-hero__main-media::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 58%, rgb(3 17 35 / 64%));
  content: '';
  pointer-events: none;
}

.presentation-hero__main-media :deep(img) {
  aspect-ratio: 4 / 3;
}

.presentation-hero__product-tags {
  position: absolute;
  right: -1.5rem;
  bottom: -1.5rem;
  width: min(24rem, 86%);
  display: grid;
  background: rgb(255 255 255 / 96%);
  border-top: 3px solid #268fec;
  box-shadow: 0 1.4rem 3rem rgb(0 9 22 / 35%);
}

.presentation-hero__product-tags a {
  padding: 0.85rem 1rem;
  display: grid;
  grid-template-columns: 2rem 1fr;
  align-items: center;
  color: #0c2b4b;
  font-size: 0.82rem;
  font-weight: 750;
  text-decoration: none;
  border-bottom: 1px solid #d9e6f1;
}

.presentation-hero__product-tags a:last-child {
  border-bottom: 0;
}

.presentation-hero__product-tags span {
  color: #1684e4;
  font-family: var(--font-technical);
  font-size: 0.68rem;
}

.presentation-section {
  padding-block: clamp(4.5rem, 8vw, 7.5rem);
  border-bottom: 1px solid #e5edf4;
}

.presentation-module--soft {
  background: #f2f7fb;
}

.presentation-section.presentation-module--navy,
.presentation-rfq {
  color: #d6e7f7;
  background: var(--color-navy-900);
}

.presentation-section.presentation-module--navy :where(h2, h3),
.presentation-rfq h2 {
  color: var(--color-white);
}

.presentation-section__inner {
  display: grid;
  gap: clamp(2.5rem, 5vw, 4.5rem);
}

.presentation-heading {
  display: grid;
  grid-template-columns: 3rem minmax(0, 1fr);
  align-items: end;
  gap: var(--space-5);
}

.presentation-index {
  padding-bottom: 0.35rem;
  color: var(--color-blue-600);
  border-bottom: 2px solid var(--color-blue-600);
}

.presentation-heading > div {
  display: grid;
  gap: var(--space-2);
}

.presentation-core,
.presentation-about {
  display: grid;
  grid-template-columns: minmax(14rem, 0.32fr) minmax(0, 1fr);
  gap: clamp(2rem, 5vw, 5rem);
}

.presentation-category-rail {
  display: grid;
  align-content: start;
  border-top: 1px solid #aac2d8;
}

.presentation-category-rail a {
  padding-block: var(--space-5);
  display: grid;
  gap: var(--space-2);
  color: var(--color-navy-900);
  text-decoration: none;
  border-bottom: 1px solid #aac2d8;
}

.presentation-category-rail span {
  font-size: 1.15rem;
  font-weight: 750;
}

.presentation-category-rail small {
  color: var(--color-neutral-600);
}

.presentation-products,
.presentation-data-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-5);
}

.presentation-materials {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  overflow: hidden;
  background: #c8d8e5;
  border: 1px solid #c8d8e5;
}
.presentation-materials > a {
  position: relative;
  min-width: 0;
  padding: 1rem;
  display: grid;
  grid-template-rows: auto auto 1fr;
  gap: 0.8rem;
  color: #173651;
  background: #fff;
  text-decoration: none;
}
.presentation-materials > a > span {
  color: #147dc4;
  font-family: var(--font-technical);
  font-size: 0.7rem;
  font-weight: 800;
}
.presentation-materials :deep(img) {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}
.presentation-materials h3,
.presentation-materials p {
  margin: 0;
}
.presentation-materials p {
  margin-top: 0.35rem;
  color: #6a7a89;
  font-size: 0.78rem;
}

.presentation-applications {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(18rem, 0.85fr);
  gap: 1.5rem;
}
.presentation-applications a {
  color: inherit;
  text-decoration: none;
}
.presentation-applications__feature {
  position: relative;
  min-height: 26rem;
  overflow: hidden;
  background: #071b31;
}
.presentation-applications__feature--text-only {
  align-self: start;
  min-height: 0;
  padding: clamp(1.25rem, 3vw, 2rem);
  color: #173651;
  background: linear-gradient(135deg, rgb(232 244 252 / 96%), rgb(246 250 253 / 94%)), #e8f4fc;
  border: 1px solid #b9d4e8;
}
.presentation-applications__feature :deep(.public-image),
.presentation-applications__feature :deep(img) {
  width: 100%;
  height: 100%;
}
.presentation-applications__feature :deep(img) {
  position: absolute;
  inset: 0;
  object-fit: cover;
  opacity: 0.72;
}
.presentation-applications__feature::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 25%, rgb(3 20 37 / 92%));
  content: '';
}
.presentation-applications__feature > div {
  position: absolute;
  z-index: 1;
  right: 0;
  bottom: 0;
  left: 0;
  padding: 1.5rem;
  color: #fff;
}
.presentation-applications__feature--text-only::after {
  display: none;
}
.presentation-applications__feature--text-only > div {
  position: static;
  padding: 0;
  color: #173651;
}
.presentation-applications__feature h3 {
  margin-block: 0.35rem;
  color: #fff;
  font-size: 1.6rem;
}
.presentation-applications__feature--text-only h3 {
  color: #092946;
}
.presentation-applications__feature--text-only .eyebrow {
  color: #147dc4;
}
.presentation-applications__feature--text-only > div > p:last-child {
  margin: 0;
  color: #526c80;
  line-height: 1.75;
}
.presentation-applications__list {
  display: grid;
  align-content: start;
  border-top: 1px solid #afc3d3;
}
.presentation-applications__list a {
  padding-block: 0.85rem;
  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr) auto;
  gap: 0.75rem;
  border-bottom: 1px solid #afc3d3;
}
.presentation-applications__list span,
.presentation-applications__list b {
  color: #147dc4;
  font-family: var(--font-technical);
  font-size: 0.7rem;
}
.presentation-applications__list h3,
.presentation-applications__list p {
  margin: 0;
}
.presentation-applications__list p {
  margin-top: 0.2rem;
  color: #64778a;
  font-size: 0.76rem;
}

.presentation-technologies {
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  list-style: none;
  border-top: 1px solid rgb(151 193 227 / 42%);
}
.presentation-technologies li {
  border-right: 1px solid rgb(151 193 227 / 32%);
  border-bottom: 1px solid rgb(151 193 227 / 32%);
}
.presentation-technologies a {
  min-height: 12rem;
  padding: 1.25rem;
  display: grid;
  align-content: space-between;
  gap: 1rem;
  color: inherit;
  text-decoration: none;
}
.presentation-technologies span {
  color: #76bff4;
  font-family: var(--font-technical);
  font-size: 0.7rem;
}
.presentation-technologies h3,
.presentation-technologies p {
  margin: 0;
}
.presentation-technologies p {
  margin-top: 0.4rem;
  color: #9ebbd2;
  font-size: 0.78rem;
}

.presentation-factory {
  display: grid;
  gap: var(--space-8);
}

.presentation-video-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.presentation-video-grid article {
  overflow: hidden;
  background: #061a30;
  border: 1px solid #244764;
  box-shadow: 0 1.4rem 3rem rgb(0 12 28 / 24%);
}

.presentation-video-grid article > div {
  padding: var(--space-5);
}

.presentation-video-grid h3 {
  margin-top: var(--space-2);
  color: #fff;
  font-size: 1.15rem;
}

.presentation-video-grid :deep(video) {
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.presentation-equipment-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid #9db6cc;
}

.presentation-equipment-rail article {
  padding: var(--space-5);
  border-right: 1px solid #c6d5e2;
  border-bottom: 1px solid #c6d5e2;
}

.presentation-equipment-rail article:nth-child(3n) {
  border-right: 0;
}

.presentation-products article,
.presentation-data-grid article {
  min-width: 0;
  overflow: hidden;
  background: var(--color-white);
  border: 1px solid #d8e3ec;
  box-shadow: 0 0.8rem 2rem rgb(7 33 59 / 6%);
}

.presentation-products__image,
.presentation-data-grid article > :deep(.public-image) {
  display: block;
  background: #edf5fb;
}

.presentation-products :deep(img),
.presentation-data-grid :deep(img) {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
}

.presentation-products article > div,
.presentation-data-grid article:not(:has(> .public-image)) {
  padding: var(--space-5);
}

.presentation-products article > div,
.presentation-data-grid article {
  display: grid;
  align-content: start;
  gap: var(--space-3);
}

.presentation-data-grid article > :not(.public-image) {
  margin-inline: var(--space-5);
}

.presentation-data-grid article > :last-child {
  margin-bottom: var(--space-5);
}

.presentation-products h3 a,
.presentation-data-grid h3 a {
  color: var(--color-navy-900);
  text-decoration: none;
}

.presentation-products p:not(.eyebrow),
.presentation-data-grid p:not(.eyebrow) {
  color: var(--color-neutral-600);
}

.presentation-text-link {
  color: var(--color-blue-700);
  font-weight: 750;
  text-decoration: none;
}

.presentation-about {
  grid-template-columns: minmax(8rem, 0.3fr) minmax(0, 1fr);
  align-items: start;
}

.presentation-about__marker {
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, var(--color-navy-900), var(--color-blue-600));
  font-family: var(--font-technical);
  font-size: clamp(2.4rem, 5vw, 5rem);
  font-weight: 800;
  letter-spacing: -0.08em;
}

.presentation-about > div:last-child {
  max-width: 50rem;
  display: grid;
  gap: var(--space-5);
  color: var(--color-neutral-700);
  font-size: clamp(1rem, 1.5vw, 1.16rem);
}
.presentation-about__advantages {
  margin: 0;
  padding: 0;
  display: grid;
  gap: 1px;
  list-style: none;
  background: #cbdbe7;
  border: 1px solid #cbdbe7;
}
.presentation-about__advantages li {
  padding: 0.9rem 1rem;
  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr);
  gap: 0.8rem;
  color: #173651;
  background: #fff;
}
.presentation-about__advantages span {
  color: #147dc4;
  font-family: var(--font-technical);
  font-size: 0.7rem;
  font-weight: 800;
}
.presentation-about__advantages strong {
  font-size: 0.94rem;
  font-weight: 750;
  line-height: 1.55;
}
.presentation-about__facts {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  background: #cbdbe7;
  border: 1px solid #cbdbe7;
}
.presentation-about__facts > div {
  padding: 0.8rem;
  background: #fff;
}
.presentation-about__facts dt {
  color: #718396;
  font-size: 0.68rem;
}
.presentation-about__facts dd {
  margin: 0.15rem 0 0;
  color: #113b5b;
  font-size: 1rem;
  font-weight: 800;
}

.presentation-empty {
  min-height: 7rem;
  padding: var(--space-6);
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-5);
  color: var(--color-neutral-600);
  background: rgb(255 255 255 / 68%);
  border: 1px dashed #9cb4c8;
}

.presentation-empty > span {
  width: 2.4rem;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  color: var(--color-blue-700);
  border: 1px solid #9cb4c8;
  border-radius: 50%;
}

.presentation-empty a {
  font-weight: 700;
}

.presentation-empty--dark {
  color: #d6e7f7;
  background: rgb(3 17 35 / 50%);
  border-color: rgb(255 255 255 / 34%);
}

.presentation-markets {
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  list-style: none;
}

.presentation-markets li {
  padding: 0.65rem 1rem;
  background: var(--color-blue-50);
  border: 1px solid var(--color-blue-100);
}

.presentation-markets .presentation-markets__note {
  flex-basis: 100%;
  color: #c6def4;
  background: transparent;
  border-color: rgb(161 206 245 / 24%);
}

.presentation-rfq {
  padding-block: clamp(4rem, 8vw, 7rem);
  background:
    linear-gradient(115deg, rgb(7 24 43 / 98%), rgb(8 79 158 / 88%)), var(--color-navy-900);
}

.presentation-rfq__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
}

.presentation-rfq__inner > div {
  max-width: 48rem;
  display: grid;
  gap: var(--space-3);
}

.presentation-rfq__inner p:last-child {
  color: #d6e7f7;
}

@media (max-width: 64rem) {
  .presentation-hero__grid {
    grid-template-columns: minmax(0, 1fr) minmax(15rem, 0.8fr);
  }

  .presentation-hero__visual {
    min-height: 25rem;
  }

  .presentation-products,
  .presentation-data-grid,
  .presentation-materials,
  .presentation-technologies,
  .presentation-equipment-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .presentation-equipment-rail article:nth-child(3n) {
    border-right: 1px solid #c6d5e2;
  }

  .presentation-equipment-rail article:nth-child(2n) {
    border-right: 0;
  }
}

@media (max-width: 48rem) {
  .preview-notice {
    position: static;
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-1);
  }

  .presentation-hero {
    min-height: auto;
  }

  .presentation-hero__grid,
  .presentation-core,
  .presentation-about,
  .presentation-applications {
    grid-template-columns: minmax(0, 1fr);
  }

  .presentation-hero__grid {
    padding-block: 4.5rem 3rem;
    gap: var(--space-10);
  }

  .presentation-hero__visual {
    min-height: 22rem;
  }

  .presentation-hero__visual:has(.presentation-hero__main-media) {
    min-height: auto;
    padding-bottom: 5rem;
  }

  .presentation-hero__product-tags {
    right: 0;
    bottom: 0;
  }

  .presentation-video-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .presentation-heading {
    grid-template-columns: 2.4rem minmax(0, 1fr);
  }

  .presentation-rfq__inner {
    align-items: stretch;
    flex-direction: column;
  }
}

@media (max-width: 30rem) {
  .presentation-actions,
  .presentation-products,
  .presentation-data-grid,
  .presentation-materials,
  .presentation-technologies,
  .presentation-equipment-rail,
  .presentation-empty {
    grid-template-columns: minmax(0, 1fr);
  }

  .presentation-actions {
    display: grid;
  }

  .presentation-hero__visual {
    min-height: 19rem;
  }

  .presentation-hero__visual:has(.presentation-hero__main-media) {
    min-height: auto;
  }

  .presentation-hero__visual > figure {
    width: 62%;
  }

  .presentation-empty {
    justify-items: start;
  }
}
</style>
