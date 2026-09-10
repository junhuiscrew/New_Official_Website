<!-- 页面用途：展示公司公开联系资料与RFQ入口；Demo邮箱只展示不创建mailto发送动作。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { resolveRouteLocale } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { PublicCompanyProfileDto } from '~/types/public'

interface CompanyEnvelope {
  success: boolean
  data: PublicCompanyProfileDto | null
}

const route = useRoute()
const api = useApi()
const runtimeConfig = useRuntimeConfig()
const locale = computed(() => resolveRouteLocale(route.params.lang, route.path))
const labels = computed(() => ui[locale.value])
const { data: response } = await useAsyncData(
  () => `contact:${locale.value}`,
  () => api<CompanyEnvelope>(`/public/company-profile/${locale.value}`),
)
const company = computed(() => (response.value?.success ? response.value.data : null))
const demoMode = computed(() => Boolean(runtimeConfig.public.demoMode))
const contactSummary = computed(() =>
  demoMode.value ? labels.value.home.demoContactSummary : labels.value.home.contactSummary,
)

useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: `${labels.value.navigation.contact} · ${company.value?.company_name || 'Junhui'}`,
  meta: [
    { name: 'description', content: contactSummary.value },
    { name: 'robots', content: 'noindex, nofollow' },
  ],
}))
</script>

<template>
  <div class="contact-page">
    <section class="contact-hero">
      <div class="public-container">
        <p>{{ labels.presentation.contactRfqLabel }}</p>
        <h1>{{ labels.home.contactTitle }}</h1>
        <span>{{ contactSummary }}</span>
      </div>
    </section>
    <section class="public-section">
      <div class="public-container contact-grid">
        <article class="contact-card contact-card--primary">
          <p>01 / {{ labels.presentation.moduleNames.rfq_cta }}</p>
          <h2>{{ labels.cta.requestQuote }}</h2>
          <span>{{ demoMode ? labels.home.demoRfqSummary : labels.home.rfqSummary }}</span>
          <a :href="`/${locale}/request-a-quote/`"
            >{{ demoMode ? labels.home.demoRfqAction : labels.cta.requestQuote }} →</a
          >
        </article>
        <article class="contact-card">
          <p>02 / {{ labels.presentation.companyLabel }}</p>
          <h2>{{ company?.company_name || 'Junhui' }}</h2>
          <dl>
            <div v-if="company?.email">
              <dt>{{ labels.form.email }}</dt>
              <dd>
                <span v-if="demoMode">{{ company.email }} · DEMO</span
                ><a v-else :href="`mailto:${company.email}`">{{ company.email }}</a>
              </dd>
            </div>
            <div v-if="company?.phone">
              <dt>{{ labels.form.phone }}</dt>
              <dd>{{ company.phone }}</dd>
            </div>
            <div v-if="company?.address">
              <dt>{{ locale === 'zh-cn' ? '地址' : 'Address' }}</dt>
              <dd>{{ company.address }}</dd>
            </div>
          </dl>
        </article>
        <article class="contact-card">
          <p>03 / {{ labels.presentation.resourcesLabel }}</p>
          <h2>{{ labels.navigation.downloads }}</h2>
          <span>{{ labels.trust.downloadsIntro }}</span>
          <a :href="`/${locale}/downloads/`">{{ labels.cta.download }} →</a>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.contact-hero {
  padding-block: clamp(4rem, 9vw, 7rem);
  color: #d9ebf9;
  background: linear-gradient(110deg, #06182b, #0a4d83);
}
.contact-hero .public-container {
  display: grid;
  gap: 1rem;
}
.contact-hero p {
  margin: 0;
  color: #74c8f5;
  font-size: 0.7rem;
  font-weight: 850;
  letter-spacing: 0.15em;
}
.contact-hero h1 {
  max-width: 14ch;
  color: #fff;
  font-size: clamp(2.2rem, 5vw, 4.8rem);
  letter-spacing: -0.055em;
}
.contact-hero span {
  max-width: 48rem;
  color: #c4d9e9;
  font-size: 1.05rem;
  line-height: 1.75;
}
.contact-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.95fr 0.9fr;
  gap: 1rem;
}
.contact-card {
  min-height: 19rem;
  padding: clamp(1.3rem, 3vw, 2rem);
  display: grid;
  align-content: start;
  gap: 1rem;
  background: #fff;
  border: 1px solid #d8e4ed;
}
.contact-card--primary {
  color: #d8e8f7;
  background: #081d33;
  border-color: #081d33;
}
.contact-card p {
  margin: 0;
  color: #1479c9;
  font-size: 0.66rem;
  font-weight: 850;
  letter-spacing: 0.13em;
}
.contact-card h2 {
  color: #102943;
  font-size: 1.45rem;
}
.contact-card--primary h2 {
  color: #fff;
}
.contact-card > span,
.contact-card dd {
  color: #66798c;
  line-height: 1.65;
}
.contact-card--primary > span {
  color: #b9d0e3;
}
.contact-card > a {
  margin-top: auto;
  color: #0c6bb8;
  font-weight: 800;
  text-decoration: none;
}
.contact-card--primary > a {
  color: #71cff8;
}
.contact-card dl {
  margin: 0;
  display: grid;
  gap: 0.8rem;
}
.contact-card dl > div {
  display: grid;
  gap: 0.25rem;
}
.contact-card dt {
  color: #8090a0;
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
}
.contact-card dd {
  margin: 0;
}
.contact-card dd a {
  color: #0d6bb7;
}
@media (max-width: 50rem) {
  .contact-grid {
    grid-template-columns: 1fr;
  }
  .contact-card {
    min-height: auto;
  }
}
</style>
