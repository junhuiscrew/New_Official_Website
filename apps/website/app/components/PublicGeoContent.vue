<!-- 组件职责：将 GEO 直接答案、关键事实与证据作为用户可见内容展示。 -->
<script setup lang="ts">
defineProps<{
  geo: {
    direct_answer?: string | null
    key_facts?: string[]
    evidence?: string[]
    related_questions?: string[]
    last_reviewed_at?: string | null
  } | null
}>()
</script>

<template>
  <section v-if="geo" class="public-geo" aria-labelledby="direct-answer-heading">
    <h2 id="direct-answer-heading">Direct answer</h2>
    <p class="direct-answer">{{ geo.direct_answer }}</p>
    <template v-if="geo.key_facts?.length">
      <h3>Key facts</h3>
      <ul>
        <li v-for="fact in geo.key_facts" :key="fact">{{ fact }}</li>
      </ul>
    </template>
    <template v-if="geo.evidence?.length">
      <h3>Evidence</h3>
      <ul>
        <li v-for="item in geo.evidence" :key="item">{{ item }}</li>
      </ul>
    </template>
    <p v-if="geo.last_reviewed_at">
      <small>Last reviewed: {{ geo.last_reviewed_at }}</small>
    </p>
  </section>
</template>
