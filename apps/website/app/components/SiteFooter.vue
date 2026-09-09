<!-- 组件职责：按 Navigation API 的真实 Company 字段条件渲染全局 Footer。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, NavigationDto } from '~/types/public'
import { telephoneHref } from '~/utils/contact'

const props = withDefaults(
  defineProps<{
    navigation: NavigationDto
    locale: LocaleSlug
    termsUrl?: string | null
    year?: number
  }>(),
  { termsUrl: null, year: () => new Date().getUTCFullYear() },
)

const labels = computed(() => ui[props.locale])
const company = computed(() => props.navigation.company)
const primary = computed(() => new Set(props.navigation.primary))
// 演示环境可使用“演示联系电话”等展示标签；只有真实号码格式才输出可拨号链接。
const phoneHref = computed(() => telephoneHref(company.value?.phone))
</script>

<template>
  <footer class="site-footer">
    <div class="site-footer__grid">
      <section v-if="company" class="site-footer__company">
        <h2>{{ labels.footer.company }}</h2>
        <strong>{{ company.name }}</strong>
        <address>
          <a v-if="phoneHref" :href="phoneHref">{{ company.phone }}</a>
          <span v-else-if="company.phone">{{ company.phone }}</span>
          <a v-if="company.email && !navigation.demo_mode" :href="`mailto:${company.email}`">{{
            company.email
          }}</a>
          <span v-else-if="company.email">{{ company.email }} · DEMO</span>
          <span v-if="company.address">{{ company.address }}</span>
        </address>
      </section>

      <section>
        <h2>{{ labels.navigation.products }}</h2>
        <ul>
          <li>
            <a :href="`/${locale}/products/`">{{ labels.navigation.viewAllProducts }}</a>
          </li>
        </ul>
      </section>

      <section v-if="primary.has('solutions')">
        <h2>{{ labels.navigation.solutions }}</h2>
        <ul>
          <li>
            <a :href="`/${locale}/solutions/`">{{ labels.navigation.solutions }}</a>
          </li>
        </ul>
      </section>

      <section v-if="primary.has('knowledge')">
        <h2>{{ labels.navigation.knowledge }}</h2>
        <ul>
          <li>
            <a :href="`/${locale}/knowledge/`">{{ labels.navigation.knowledge }}</a>
          </li>
        </ul>
      </section>

      <section>
        <h2>{{ labels.footer.contact }}</h2>
        <ul>
          <li>
            <a :href="`/${locale}/contact/`">{{ labels.navigation.contact }}</a>
          </li>
          <li>
            <a :href="`/${locale}/request-a-quote/`">{{ labels.cta.requestQuote }}</a>
          </li>
          <li>
            <a :href="`/${locale}/downloads/`">{{ labels.navigation.downloads }}</a>
          </li>
        </ul>
      </section>

      <section>
        <h2>{{ labels.footer.legal }}</h2>
        <ul>
          <li>
            <a :href="`/${locale}/privacy/`">{{ labels.footer.privacy }}</a>
          </li>
          <li v-if="termsUrl">
            <a :href="termsUrl">{{ labels.footer.terms }}</a>
          </li>
          <li>
            <a href="/sitemap.xml">{{ labels.footer.sitemap }}</a>
          </li>
        </ul>
      </section>

      <section>
        <h2>{{ labels.footer.language }}</h2>
        <ul>
          <li>
            <a href="/zh-cn/" lang="zh-CN">{{ labels.language.zhCn }}</a>
          </li>
          <li>
            <a href="/en/" lang="en">{{ labels.language.en }}</a>
          </li>
        </ul>
      </section>
    </div>

    <div class="site-footer__bottom">
      <p>
        © {{ year }}<template v-if="company"> {{ company.name }}</template
        >. {{ labels.footer.copyright }}.
      </p>
    </div>
  </footer>
</template>

<style scoped>
.site-footer {
  color: var(--color-neutral-200);
  background: var(--color-navy-950);
  border-block-start: 3px solid var(--color-blue-600);
}

.site-footer__grid,
.site-footer__bottom {
  width: min(calc(100% - var(--space-8)), var(--container-max));
  margin-inline: auto;
}

.site-footer__grid {
  padding-block: var(--space-10);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: var(--space-8);
}

.site-footer__company {
  grid-column: span 2;
}

.site-footer h2 {
  margin: 0 0 var(--space-3);
  color: var(--color-white);
  font-size: var(--font-size-label);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.site-footer strong {
  color: var(--color-white);
}

.site-footer address,
.site-footer ul {
  margin: var(--space-3) 0 0;
  padding: 0;
  display: grid;
  gap: var(--space-2);
  font-style: normal;
  list-style: none;
}

.site-footer a {
  color: inherit;
  text-decoration: none;
}

.site-footer a:hover {
  color: var(--color-blue-100);
}

.site-footer__bottom {
  padding-block: var(--space-4);
  color: var(--color-neutral-400);
  border-block-start: 1px solid var(--color-navy-700);
}

.site-footer__bottom p {
  margin: 0;
  font-size: var(--font-size-small);
}

@media (max-width: 32rem) {
  .site-footer__grid,
  .site-footer__bottom {
    width: min(calc(100% - var(--space-6)), var(--container-max));
  }

  .site-footer__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .site-footer__company {
    grid-column: 1 / -1;
  }
}
</style>
