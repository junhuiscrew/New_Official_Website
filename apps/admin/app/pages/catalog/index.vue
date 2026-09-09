<!-- 页面用途：汇总结构化内容模块、真实记录数与可搜索维护入口。 -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { adminMeta } from '../../admin-config'

interface CatalogModule {
  key: string
  code: string
  title: string
  description: string
  path: string
  endpoint: string
  count: number | null
}

const api = useCatalogApi()
const moduleSearch = ref('')
const loading = ref(true)
const loadWarnings = ref<string[]>([])
const catalogModules = ref<CatalogModule[]>([
  {
    key: 'products',
    code: 'PR',
    title: '产品与型号',
    description: '双语正文、主图、型号、参数、关系与发布状态。',
    path: '/catalog/products',
    endpoint: '/catalog/products?page=1&page_size=1',
    count: null,
  },
  {
    key: 'categories',
    code: 'CA',
    title: '产品分类',
    description: '维护分类名称、Slug、排序及双语公开状态。',
    path: '/catalog/categories',
    endpoint: '/catalog/categories?page=1&page_size=1',
    count: null,
  },
  {
    key: 'materials',
    code: 'MA',
    title: '材料',
    description: '维护材料说明及其与产品、方案的结构化关系。',
    path: '/catalog/materials',
    endpoint: '/catalog/materials?page=1&page_size=1',
    count: null,
  },
  {
    key: 'technologies',
    code: 'TE',
    title: '工艺技术',
    description: '维护工艺说明、媒体及产品技术关系。',
    path: '/catalog/technologies',
    endpoint: '/catalog/technologies?page=1&page_size=1',
    count: null,
  },
  {
    key: 'applications',
    code: 'AP',
    title: '应用场景',
    description: '维护行业应用内容及产品筛选关系。',
    path: '/catalog/applications',
    endpoint: '/catalog/applications?page=1&page_size=1',
    count: null,
  },
  {
    key: 'solutions',
    code: 'SO',
    title: '解决方案',
    description: '维护方案正文、关联对象与发布生命周期。',
    path: '/catalog/solutions',
    endpoint: '/catalog/solutions?page=1&page_size=1',
    count: null,
  },
  {
    key: 'specifications',
    code: 'SP',
    title: '规格与参数字典',
    description: '管理参数分组、名称、类型、单位及产品参数值。',
    path: '/catalog/specifications',
    endpoint: '/catalog/specifications/definitions?page=1&page_size=1',
    count: null,
  },
])

const filteredModules = computed(() => {
  const needle = moduleSearch.value.trim().toLocaleLowerCase()
  if (!needle) return catalogModules.value
  return catalogModules.value.filter((item) =>
    [item.title, item.description, item.key, item.code]
      .join(' ')
      .toLocaleLowerCase()
      .includes(needle),
  )
})
const totalRecords = computed(() =>
  catalogModules.value.reduce((total, item) => total + (item.count ?? 0), 0),
)

/** 逐模块读取实时总数；单项权限失败不会遮住其他维护入口。 */
async function loadCounts(): Promise<void> {
  loading.value = true
  const results = await Promise.allSettled(
    catalogModules.value.map((item) => api.list<unknown>(item.endpoint)),
  )
  results.forEach((result, index) => {
    const module = catalogModules.value[index]
    if (!module) return
    if (result.status === 'fulfilled') module.count = result.value.total
    else loadWarnings.value.push(module.title)
  })
  loading.value = false
}

// Admin 页面统一禁止搜索引擎收录；真正权限仍由 FastAPI RBAC 校验。
useHead({
  title: `内容目录 · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
onMounted(loadCounts)
</script>

<template>
  <main class="admin-shell catalog-hub">
    <header class="catalog-hub__hero">
      <div>
        <p>STRUCTURED CONTENT</p>
        <h1>内容目录</h1>
        <span>从一个入口查找产品、分类、材料、工艺、应用、方案和规格字典。</span>
      </div>
      <dl>
        <div>
          <dt>模块</dt>
          <dd>{{ catalogModules.length }}</dd>
        </div>
        <div>
          <dt>当前记录</dt>
          <dd>{{ loading ? '—' : totalRecords }}</dd>
        </div>
      </dl>
    </header>

    <section class="catalog-hub__toolbar">
      <label>
        <span>搜索管理模块</span>
        <input v-model="moduleSearch" type="search" placeholder="例如：产品、工艺、参数" />
      </label>
      <p v-if="loadWarnings.length" role="status">
        {{ loadWarnings.join('、') }}计数暂不可用，入口仍可正常打开。
      </p>
    </section>

    <nav class="catalog-hub__grid" aria-label="结构化内容模块">
      <NuxtLink v-for="item in filteredModules" :key="item.key" :to="item.path">
        <span class="catalog-hub__code">{{ item.code }}</span>
        <div>
          <h2>{{ item.title }}</h2>
          <p>{{ item.description }}</p>
        </div>
        <strong>{{ item.count === null ? '—' : item.count }}</strong>
        <small>打开维护 →</small>
      </NuxtLink>
    </nav>
    <p v-if="!filteredModules.length" class="catalog-hub__empty">没有匹配的管理模块。</p>
  </main>
</template>

<style scoped>
.catalog-hub {
  display: grid;
  align-content: start;
  gap: 1.15rem;
}
.catalog-hub__hero {
  padding: 1.5rem 1.7rem;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1.5rem;
  color: #d7e9f8;
  background: linear-gradient(112deg, #07192d, #0a4c84);
  border-radius: 0.95rem;
}
.catalog-hub__hero p,
.catalog-hub__hero h1 {
  margin: 0;
  color: #fff;
}
.catalog-hub__hero p {
  color: #69c9f4;
  font-size: 0.66rem;
  font-weight: 850;
  letter-spacing: 0.14em;
}
.catalog-hub__hero h1 {
  margin-block: 0.25rem 0.45rem;
  font-size: clamp(1.65rem, 3vw, 2.5rem);
}
.catalog-hub__hero dl {
  margin: 0;
  display: flex;
  gap: 0.7rem;
}
.catalog-hub__hero dl > div {
  min-width: 6.5rem;
  padding: 0.75rem;
  background: rgb(2 17 32 / 38%);
  border: 1px solid rgb(129 200 242 / 26%);
  border-radius: 0.65rem;
}
.catalog-hub__hero dt {
  color: #9dc8e5;
  font-size: 0.66rem;
}
.catalog-hub__hero dd {
  margin: 0.2rem 0 0;
  color: #fff;
  font-size: 1.35rem;
  font-weight: 800;
}
.catalog-hub__toolbar {
  padding: 0.9rem 1rem;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
  background: #fff;
  border: 1px solid #dce5ed;
  border-radius: 0.75rem;
}
.catalog-hub__toolbar label {
  width: min(30rem, 100%);
  display: grid;
  gap: 0.35rem;
  color: #486079;
  font-size: 0.72rem;
}
.catalog-hub__toolbar p {
  margin: 0;
  color: #9a5e0a;
  font-size: 0.72rem;
}
.catalog-hub__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}
.catalog-hub__grid a {
  min-height: 12.5rem;
  padding: 1.15rem;
  display: grid;
  grid-template-columns: auto 1fr auto;
  grid-template-rows: 1fr auto;
  align-items: start;
  gap: 0.85rem;
  color: #18334e;
  background: #fff;
  border: 1px solid #d8e3ec;
  border-radius: 0.85rem;
  box-shadow: 0 0.7rem 1.7rem rgb(21 54 84 / 5%);
  text-decoration: none;
}
.catalog-hub__grid a:hover {
  border-color: #2791d8;
  transform: translateY(-2px);
}
.catalog-hub__code {
  width: 2.35rem;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  color: #0b65a8;
  background: #e7f5ff;
  border-radius: 0.55rem;
  font-size: 0.68rem;
  font-weight: 850;
}
.catalog-hub__grid h2,
.catalog-hub__grid p {
  margin: 0;
}
.catalog-hub__grid h2 {
  font-size: 1rem;
}
.catalog-hub__grid p {
  margin-top: 0.4rem;
  color: #697c8f;
  font-size: 0.76rem;
  line-height: 1.6;
}
.catalog-hub__grid strong {
  color: #0b65a8;
  font-size: 1.4rem;
}
.catalog-hub__grid small {
  grid-column: 1 / -1;
  color: #0b65a8;
  font-weight: 750;
}
.catalog-hub__empty {
  padding: 2rem;
  text-align: center;
  background: #fff;
  border: 1px dashed #a9bdcd;
}
@media (max-width: 65rem) {
  .catalog-hub__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 44rem) {
  .catalog-hub__hero,
  .catalog-hub__toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .catalog-hub__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
