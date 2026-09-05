<!-- 组件职责：把后端 GEO 直接答案、关键事实、证据和相关问题完整呈现给用户。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { GeoDto, LocaleSlug } from '~/types/public'

const props = defineProps<{
  locale: LocaleSlug
  geo: GeoDto | null
}>()
const labels = computed(() => ui[props.locale])

/** 只接受 DTO 中非空字符串，避免把任意对象或空值作为隐藏 GEO 内容输出。 */
function visibleText(items: string[] | undefined): string[] {
  return (items ?? []).filter((item) => typeof item === 'string' && Boolean(item.trim()))
}

const directAnswer = computed(() => props.geo?.direct_answer?.trim() ?? '')
const keyFacts = computed(() => visibleText(props.geo?.key_facts))
const evidence = computed(() => visibleText(props.geo?.evidence))
const relatedQuestions = computed(() => visibleText(props.geo?.related_questions))
const hasVisibleContent = computed(
  () =>
    Boolean(directAnswer.value) ||
    keyFacts.value.length > 0 ||
    evidence.value.length > 0 ||
    relatedQuestions.value.length > 0,
)
</script>

<template>
  <section v-if="hasVisibleContent" class="geo-answer" aria-labelledby="geo-answer-heading">
    <h2 id="geo-answer-heading">{{ labels.sections.quickAnswer }}</h2>
    <div v-if="directAnswer" class="geo-answer__direct">
      <p>{{ directAnswer }}</p>
    </div>

    <section v-if="keyFacts.length" class="geo-answer__group">
      <h3>{{ labels.sections.keyFacts }}</h3>
      <ul>
        <li v-for="fact in keyFacts" :key="fact">{{ fact }}</li>
      </ul>
    </section>

    <section v-if="evidence.length" class="geo-answer__group">
      <h3>{{ labels.sections.evidence }}</h3>
      <ul>
        <li v-for="item in evidence" :key="item">{{ item }}</li>
      </ul>
    </section>

    <section v-if="relatedQuestions.length" class="geo-answer__group">
      <h3>{{ labels.sections.relatedQuestions }}</h3>
      <ul>
        <li v-for="question in relatedQuestions" :key="question">{{ question }}</li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.geo-answer {
  padding: clamp(var(--space-6), 5vw, var(--space-10));
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
  background: var(--color-neutral-100);
  border-block-start: 3px solid var(--color-blue-600);
}

.geo-answer__direct {
  grid-column: 1 / -1;
}

.geo-answer > h2 {
  grid-column: 1 / -1;
}

.geo-answer__direct p {
  max-width: 54rem;
  margin-block-start: var(--space-3);
  color: var(--color-neutral-700);
  font-size: clamp(1rem, 2vw, 1.125rem);
}

.geo-answer__group {
  margin: 0;
}

.geo-answer ul {
  margin: var(--space-3) 0 0;
  padding-inline-start: var(--space-5);
}

@media (max-width: 48rem) {
  .geo-answer {
    grid-template-columns: minmax(0, 1fr);
  }

  .geo-answer__direct {
    grid-column: auto;
  }
}
</style>
