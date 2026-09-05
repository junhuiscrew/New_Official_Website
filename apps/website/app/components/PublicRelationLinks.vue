<!-- 组件职责：把后端已通过公开门槛过滤的白名单关系渲染为本地化 canonical anchors。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug } from '~/types/public'

interface RelationLinkDto {
  type: string
  slug: string
  name: string
  url: string
  summary: string
}

const props = withDefaults(
  defineProps<{
    relations: Record<string, RelationLinkDto[]>
    locale?: LocaleSlug
    heading?: string
  }>(),
  { locale: 'en', heading: undefined },
)
const labels = computed(() => ui[props.locale])
const relationLabels = computed<Record<string, string>>(() => ({
  materials: labels.value.navigation.materials,
  technologies: labels.value.sections.technologies,
  applications: labels.value.navigation.applications,
  solutions: labels.value.navigation.solutions,
  capabilities: labels.value.navigation.capabilities,
  cases: labels.value.sections.caseStudies,
  case_studies: labels.value.sections.caseStudies,
  knowledge: labels.value.sections.technicalKnowledge,
  knowledge_articles: labels.value.sections.technicalKnowledge,
}))
const visibleGroups = computed(() =>
  Object.entries(props.relations)
    .filter(([key, links]) => Boolean(relationLabels.value[key]) && links.length > 0)
    .map(([key, links]) => ({ key, label: relationLabels.value[key]!, links })),
)
</script>

<template>
  <section v-if="visibleGroups.length" class="public-relations">
    <h2>{{ heading ?? labels.sections.relatedContent }}</h2>
    <section v-for="group in visibleGroups" :key="group.key">
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
