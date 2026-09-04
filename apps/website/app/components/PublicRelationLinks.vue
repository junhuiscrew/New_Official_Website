<!-- 组件职责：把后端已通过公开门槛过滤的结构化关系渲染为真实内部链接。 -->
<script setup lang="ts">
export interface PublicLinkDto {
  type: string
  slug: string
  name: string
  url: string
  summary: string
}

defineProps<{ relations: Record<string, PublicLinkDto[]> }>()
</script>

<template>
  <section v-if="Object.values(relations).some((links) => links.length)">
    <h2>Related content</h2>
    <section v-for="(links, relationName) in relations" :key="relationName">
      <template v-if="links.length">
        <h3>{{ relationName }}</h3>
        <ul>
          <li v-for="link in links" :key="`${link.type}:${link.slug}`">
            <a :href="link.url">{{ link.name }}</a>
            <p v-if="link.summary">{{ link.summary }}</p>
          </li>
        </ul>
      </template>
    </section>
  </section>
</template>
