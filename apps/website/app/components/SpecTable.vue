<!-- 组件职责：按公开分组展示后端已格式化的规格字符串，不读取或解析 ORM 原始值。 -->
<script setup lang="ts">
import { computed } from 'vue'

import type { LocaleSlug, PublicSpecDto } from '~/types/public'

const props = withDefaults(
  defineProps<{
    specifications: PublicSpecDto[]
    locale?: LocaleSlug
  }>(),
  { locale: 'en' },
)

interface SpecGroup {
  id: string
  name: string
  items: PublicSpecDto[]
}

/** 按 DTO group 保持原始顺序分组，所有值继续使用后端字符串。 */
const groups = computed<SpecGroup[]>(() => {
  const grouped = new Map<string, PublicSpecDto[]>()
  for (const specification of props.specifications) {
    const groupName = specification.group.trim() || (props.locale === 'zh-cn' ? '其他' : 'Other')
    const current = grouped.get(groupName) ?? []
    current.push(specification)
    grouped.set(groupName, current)
  }
  return [...grouped.entries()].map(([name, items], index) => ({
    id: `spec-group-${index}`,
    name,
    items,
  }))
})
</script>

<template>
  <div class="spec-table">
    <section v-for="group in groups" :key="group.id" :aria-labelledby="group.id" data-spec-group>
      <h3 :id="group.id">{{ group.name }}</h3>
      <table>
        <tbody>
          <tr v-for="item in group.items" :key="`${item.name}:${item.value}`">
            <th scope="row">{{ item.name }}</th>
            <td>
              {{ item.value }}<template v-if="item.unit"> {{ item.unit }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <dl>
        <div v-for="item in group.items" :key="`${item.name}:${item.value}:compact`">
          <dt>{{ item.name }}</dt>
          <dd>
            {{ item.value }}<template v-if="item.unit"> {{ item.unit }}</template>
          </dd>
        </div>
      </dl>
    </section>
  </div>
</template>

<style scoped>
.spec-table {
  display: grid;
  gap: var(--space-8);
}

.spec-table section,
.spec-table table {
  width: 100%;
}

.spec-table h3 {
  margin-block-end: var(--space-3);
}

.spec-table table {
  border-collapse: collapse;
}

.spec-table th,
.spec-table td {
  padding: var(--space-3) var(--space-4);
  text-align: start;
  border-block-end: var(--border-subtle);
}

.spec-table th {
  width: 45%;
  color: var(--color-neutral-700);
  font-weight: 650;
}

.spec-table td,
.spec-table dd {
  color: var(--color-neutral-950);
  font-family: var(--font-technical);
}

.spec-table dl {
  display: none;
}

@media (max-width: 36rem) {
  .spec-table table {
    display: none;
  }

  .spec-table dl {
    margin: 0;
    display: grid;
  }

  .spec-table dl > div {
    padding-block: var(--space-3);
    display: grid;
    gap: var(--space-1);
    border-block-end: var(--border-subtle);
  }

  .spec-table dd {
    margin: 0;
  }
}
</style>
