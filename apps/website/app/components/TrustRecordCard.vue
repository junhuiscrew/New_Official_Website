<!-- 组件职责：按显式白名单展示 non-route Trust 的公开事实，不生成第二套详情链接。 -->
<script setup lang="ts">
import { computed } from 'vue'

import type { LocaleSlug, PublicTrustListItemDto } from '~/types/public'

const props = defineProps<{
  locale: LocaleSlug
  item: PublicTrustListItemDto
  details?: Record<string, string | number | null>
}>()

const labels = {
  'zh-cn': {
    certificate_type: '证书类型',
    certificate_number: '证书编号',
    issuer: '颁发机构',
    issue_date: '颁发日期',
    expiry_date: '到期日期',
    patent_number: '专利号',
    patent_type: '专利类型',
    application_number: '申请号',
    filing_date: '申请日期',
    grant_date: '授权日期',
    jurisdiction: '司法辖区',
    inventor_text: '发明人',
    issuing_organization: '颁发组织',
    award_date: '获奖日期',
  },
  en: {
    certificate_type: 'Certificate Type',
    certificate_number: 'Certificate Number',
    issuer: 'Issuer',
    issue_date: 'Issue Date',
    expiry_date: 'Expiry Date',
    patent_number: 'Patent Number',
    patent_type: 'Patent Type',
    application_number: 'Application Number',
    filing_date: 'Filing Date',
    grant_date: 'Grant Date',
    jurisdiction: 'Jurisdiction',
    inventor_text: 'Inventor',
    issuing_organization: 'Issuing Organization',
    award_date: 'Award Date',
  },
} as const

/** 仅展示后端 Trust details 白名单中当前语言支持的非空事实。 */
const visibleDetails = computed(() =>
  Object.entries(props.details ?? props.item.details ?? {})
    .filter(([key, value]) => key in labels[props.locale] && value !== null && value !== '')
    .map(([key, value]) => ({
      key,
      label: labels[props.locale][key as keyof (typeof labels)[LocaleSlug]],
      value,
    })),
)
</script>

<template>
  <article class="trust-record">
    <h2>{{ item.title }}</h2>
    <p v-if="item.summary">{{ item.summary }}</p>
    <dl v-if="visibleDetails.length">
      <div v-for="detail in visibleDetails" :key="detail.key">
        <dt>{{ detail.label }}</dt>
        <dd>{{ detail.value }}</dd>
      </div>
    </dl>
  </article>
</template>

<style scoped>
.trust-record {
  padding: var(--space-6);
  display: grid;
  gap: var(--space-4);
  border: var(--border-subtle);
  border-block-start: 3px solid var(--color-blue-600);
}

.trust-record p {
  color: var(--color-neutral-600);
}

.trust-record dl {
  margin: 0;
  display: grid;
  gap: var(--space-2);
}

.trust-record dl > div {
  display: grid;
  grid-template-columns: minmax(8rem, 0.4fr) minmax(0, 1fr);
  gap: var(--space-3);
}

.trust-record dt,
.trust-record dd {
  margin: 0;
}

.trust-record dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}
</style>
