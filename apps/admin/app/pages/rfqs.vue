<!-- 页面用途：销售查看 RFQ 列表与状态入口，后台永远 noindex。 -->
<script setup lang="ts">
useHead({ title: 'RFQs', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const api = useAuthorityApi()
const items = ref<Array<Record<string, string>>>([])
const errorMessage = ref('')
onMounted(async () => {
  try {
    const result = await api.detail<{ items: Array<Record<string, string>> }>('/rfqs')
    items.value = result.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load RFQs.'
  }
})
</script>
<template>
  <main class="admin-shell">
    <h1>RFQs</h1>
    <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
    <table>
      <thead>
        <tr>
          <th>Reference</th>
          <th>Company</th>
          <th>Status</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>
            <NuxtLink :to="`/rfqs/${item.id}`">{{ item.public_reference }}</NuxtLink>
          </td>
          <td>{{ item.company_name }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </main>
</template>
