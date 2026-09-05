<!-- 组件职责：按页面白名单顺序展示后端已批准的 canonical 关系链接。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicContentType, PublicLinkDto } from '~/types/public'

export type RelationGroup =
  | 'products'
  | 'materials'
  | 'technologies'
  | 'applications'
  | 'solutions'
  | 'capabilities'
  | 'cases'
  | 'knowledge'

const props = defineProps<{
  locale: LocaleSlug
  relations: Partial<Record<RelationGroup, PublicLinkDto[]>>
  groups: RelationGroup[]
  heading?: string
}>()
const labels = computed(() => ui[props.locale])

/** 每个展示分组只接受后端相应内容类型，避免未知关系键或错配 DTO 进入页面。 */
const approvedTypes: Record<RelationGroup, readonly PublicContentType[]> = {
  products: ['product'],
  materials: ['material'],
  technologies: ['technology'],
  applications: ['application'],
  solutions: ['solution'],
  capabilities: ['manufacturing_capability'],
  cases: ['case_study'],
  knowledge: ['knowledge_article'],
}

const relationLabels = computed<Record<RelationGroup, string>>(() => ({
  products: labels.value.navigation.products,
  materials: labels.value.navigation.materials,
  technologies: labels.value.sections.technologies,
  applications: labels.value.navigation.applications,
  solutions: labels.value.navigation.solutions,
  capabilities: labels.value.navigation.capabilities,
  cases: labels.value.sections.caseStudies,
  knowledge: labels.value.sections.technicalKnowledge,
}))

/** 判断 URL 是否保持为后端 canonical 路径或正式站绝对地址。 */
function isCanonicalPublicUrl(url: string): boolean {
  return /^\/(?!\/)/.test(url) || url.startsWith('https://junhuiscrewbarrel.com/')
}

const visibleGroups = computed(() =>
  props.groups
    .filter((group, index, groups) => groups.indexOf(group) === index)
    .map((group) => ({
      key: group,
      label: relationLabels.value[group],
      links: (props.relations[group] ?? []).filter(
        (link) =>
          approvedTypes[group].includes(link.type) &&
          Boolean(link.name.trim()) &&
          isCanonicalPublicUrl(link.url),
      ),
    }))
    .filter((group) => group.links.length > 0),
)
</script>

<template>
  <section v-if="visibleGroups.length" class="relation-links">
    <h2>{{ heading ?? labels.sections.relatedContent }}</h2>
    <section v-for="group in visibleGroups" :key="group.key" class="relation-links__group">
      <h3>{{ group.label }}</h3>
      <ul>
        <li v-for="link in group.links" :key="`${link.type}:${link.slug}`">
          <a :href="link.url">{{ link.name }}</a>
          <p v-if="link.summary">{{ link.summary }}</p>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.relation-links {
  display: grid;
  gap: var(--space-6);
}

.relation-links__group {
  margin: 0;
}

.relation-links ul {
  margin: var(--space-3) 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  list-style: none;
}

.relation-links li {
  padding: var(--space-4);
  border: var(--border-subtle);
  border-inline-start: 3px solid var(--color-blue-600);
}

.relation-links a {
  color: var(--color-blue-700);
  font-weight: 750;
}

.relation-links li p {
  margin-block-start: var(--space-2);
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

@media (max-width: 40rem) {
  .relation-links ul {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
