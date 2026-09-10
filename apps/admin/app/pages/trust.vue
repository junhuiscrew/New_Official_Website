<!-- 页面用途：企业资料与制造能力总览，集中说明每类内容的维护入口。 -->
<script setup lang="ts">
useHead({
  title: '企业资料与制造能力',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

const api = useAuthorityApi()
const route = useRoute()
const resourceCards = [
  {
    label: '企业资料',
    path: '/trust/company',
    endpoint: '',
    description: '公司中英文介绍、品牌标识与联系信息',
  },
  {
    label: '制造能力',
    path: '/trust/capabilities',
    endpoint: '/trust/capabilities',
    description: '工艺能力、摘要与公开事实',
  },
  {
    label: '生产设备',
    path: '/trust/equipment',
    endpoint: '/trust/equipment',
    description: '设备类型、型号、数量与公开规格',
  },
  {
    label: '证书',
    path: '/trust/certificates',
    endpoint: '/trust/certificates',
    description: '证书范围、颁发机构与公开文件',
  },
  {
    label: '专利',
    path: '/trust/patents',
    endpoint: '/trust/patents',
    description: '专利信息与技术范围',
  },
  {
    label: '荣誉',
    path: '/trust/honors',
    endpoint: '/trust/honors',
    description: '荣誉名称、颁发组织与日期',
  },
  {
    label: '展会',
    path: '/trust/exhibitions',
    endpoint: '/trust/exhibitions',
    description: '展会信息、时间与地点',
  },
  {
    label: '媒体资源库',
    path: '/media',
    endpoint: '/media',
    description: '图片、视频、文件及双语元数据',
  },
  {
    label: '下载资料',
    path: '/downloads',
    endpoint: '/downloads',
    description: '公开下载文件及中英文摘要',
  },
]
const counts = ref<Record<string, number | null>>({})
const loading = ref(true)
const errorMessage = ref('')

/** 读取各类真实内容数量；输入无，输出 Promise<void> 并更新总览卡片。 */
async function loadCounts(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    await Promise.all(
      resourceCards.map(async (card) => {
        if (!card.endpoint) {
          counts.value[card.path] = 1
          return
        }
        const result = await api.detail<unknown>(card.endpoint)
        if (Array.isArray(result)) counts.value[card.path] = result.length
        else if (
          result &&
          typeof result === 'object' &&
          Array.isArray((result as { items?: unknown[] }).items)
        ) {
          const collection = result as { items: unknown[]; total?: number }
          counts.value[card.path] = collection.total ?? collection.items.length
        } else counts.value[card.path] = null
      }),
    )
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法读取企业资料总览。'
  } finally {
    loading.value = false
  }
}

onMounted(loadCounts)
</script>
<template>
  <main v-if="route.path === '/trust'" class="admin-shell trust-overview">
    <header>
      <p>企业内容中心</p>
      <h1>企业资料与制造能力</h1>
      <span>按业务类型进入维护页；中文员工无需查找英文资源代码。</span>
    </header>
    <p v-if="loading" role="status">正在读取内容数量…</p>
    <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
    <section class="trust-grid" aria-label="企业资料维护入口">
      <NuxtLink v-for="card in resourceCards" :key="card.path" :to="card.path">
        <strong>{{ card.label }}</strong>
        <span>{{ card.description }}</span>
        <small>内容数量：{{ counts[card.path] ?? '待读取' }}</small>
        <b>进入维护 →</b>
      </NuxtLink>
    </section>
  </main>
  <!-- 子页继续通过 Nuxt 嵌套路由渲染真实编辑器。 -->
  <NuxtPage />
</template>

<style scoped>
.trust-overview {
  display: grid;
  gap: 1.1rem;
  align-content: start;
}
.trust-overview header {
  display: grid;
  gap: 0.25rem;
}
.trust-overview header p,
.trust-overview header h1 {
  margin: 0;
}
.trust-overview header p {
  color: #0f70c9;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.trust-overview header span {
  color: #687b8e;
}
.trust-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 0.85rem;
}
.trust-grid a {
  min-height: 10rem;
  padding: 1rem;
  display: grid;
  align-content: start;
  gap: 0.55rem;
  color: #18364f;
  text-decoration: none;
  background: #fff;
  border: 1px solid #dbe5ee;
  border-radius: 0.75rem;
}
.trust-grid a:hover,
.trust-grid a:focus-visible {
  border-color: #1685d1;
  box-shadow: 0 8px 24px rgb(8 59 97 / 10%);
}
.trust-grid span,
.trust-grid small {
  color: #6b7e90;
}
.trust-grid b {
  margin-top: auto;
  color: #0f70c9;
  font-size: 0.78rem;
}
</style>
