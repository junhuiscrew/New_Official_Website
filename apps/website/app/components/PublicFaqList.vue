<!-- 组件职责：展示与页面正文一致的结构化 FAQ，不承诺搜索富结果。 -->
<script setup lang="ts">
defineProps<{ items: Array<{ question: string; answer: string }> }>()
</script>

<template>
  <section v-if="items.length" aria-labelledby="faq-heading">
    <h2 id="faq-heading">Frequently asked questions</h2>
    <details v-for="item in items" :key="item.question">
      <summary>{{ item.question }}</summary>
      <p>{{ item.answer }}</p>
    </details>
  </section>
</template>
