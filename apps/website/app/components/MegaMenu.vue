<!-- 组件职责：展示由后端 canonical Link DTO 组成的桌面 Mega Menu，不推断发布状态。 -->
<script setup lang="ts">
import { computed } from 'vue'

import type { PublicLinkDto } from '~/types/public'

export interface MegaMenuSection {
  key: string
  title: string
  items: PublicLinkDto[]
}

const props = defineProps<{
  id: string
  open: boolean
  sections: MegaMenuSection[]
  testId: string
  viewAll?: { label: string; href: string }
}>()

defineEmits<{ close: [] }>()

// 仅抑制空的动态分组，后端返回的 canonical URL 保持原样。
const visibleSections = computed(() => props.sections.filter((section) => section.items.length > 0))
</script>

<template>
  <div v-show="open" :id="id" class="mega-menu" :data-testid="testId" @keydown.esc="$emit('close')">
    <div class="mega-menu__inner">
      <section v-for="section in visibleSections" :key="section.key" class="mega-menu__section">
        <h2>{{ section.title }}</h2>
        <ul>
          <li v-for="item in section.items" :key="`${item.type}:${item.url}`">
            <a :href="item.url" @click="$emit('close')">
              <span>{{ item.name }}</span>
              <small v-if="item.summary">{{ item.summary }}</small>
            </a>
          </li>
        </ul>
      </section>
      <a v-if="viewAll" class="mega-menu__view-all" :href="viewAll.href" @click="$emit('close')">
        {{ viewAll.label }}
        <span aria-hidden="true">→</span>
      </a>
    </div>
  </div>
</template>

<style scoped>
.mega-menu {
  position: absolute;
  inset-block-start: 100%;
  inset-inline: 0;
  z-index: 30;
  color: var(--color-neutral-950);
  background: var(--color-white);
  border-block-start: 1px solid var(--color-neutral-200);
  box-shadow: var(--shadow-md);
}

.mega-menu__inner {
  width: min(calc(100% - var(--space-8)), var(--container-max));
  margin-inline: auto;
  padding: var(--space-6) 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: var(--space-8);
}

.mega-menu__section h2 {
  margin: 0 0 var(--space-3);
  color: var(--color-neutral-500);
  font-size: var(--font-size-label);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.mega-menu ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.mega-menu li + li {
  margin-block-start: var(--space-2);
}

.mega-menu a {
  color: inherit;
  text-decoration: none;
}

.mega-menu a:hover span:first-child {
  color: var(--color-blue-700);
}

.mega-menu small {
  display: block;
  margin-block-start: var(--space-1);
  color: var(--color-neutral-600);
}

.mega-menu__view-all {
  align-self: end;
  color: var(--color-blue-700) !important;
  font-weight: 700;
}
</style>
