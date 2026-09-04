<!-- 页面用途：公开 Download Resource 管理入口。 -->
<script setup lang="ts">
useHead({ title: 'Downloads', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const api = useAuthorityApi()
const items = ref<Array<Record<string, unknown>>>([])
const media = ref<Array<Record<string, unknown>>>([])
const translationsJson = ref('[]')
const editingId = ref<string | null>(null)
const form = reactive({
  slug: '',
  resource_type: 'document',
  status: 'enabled',
  media_asset_id: '',
  version_label: '',
  published_date: '',
  requires_form: false,
  sort_order: 0,
  translations: [] as Array<Record<string, unknown>>,
})
async function load() {
  const result = await api.detail<{ items: Array<Record<string, unknown>> }>('/downloads')
  items.value = result.items
  media.value = await api.detail('/media')
}
async function save() {
  form.translations = JSON.parse(translationsJson.value) as Array<Record<string, unknown>>
  if (editingId.value) await api.update(`/downloads/${editingId.value}`, form)
  else await api.create('/downloads', form)
  editingId.value = null
  await load()
}
function edit(item: Record<string, unknown>) {
  editingId.value = String(item.id)
  Object.assign(form, item)
  translationsJson.value = JSON.stringify(
    ((item.translations as Array<Record<string, unknown>>) || []).map((translation) => ({
      locale_id: translation.locale_id,
      fields: { title: translation.title, summary: translation.summary },
    })),
    null,
    2,
  )
}
async function archive(id: unknown) {
  await api.archive(`/downloads/${id}/archive`)
  await load()
}
onMounted(load)
</script>
<template>
  <main class="admin-shell">
    <h1>Downloads</h1>
    <form @submit.prevent="save">
      <label>Slug <input v-model="form.slug" required /></label
      ><label>Type <input v-model="form.resource_type" /></label
      ><label
        >Public media
        <select v-model="form.media_asset_id" required>
          <option v-for="asset in media" :key="String(asset.id)" :value="String(asset.id)">
            {{ asset.file_extension }} · {{ asset.id }}
          </option>
        </select></label
      ><label>Version <input v-model="form.version_label" /></label
      ><label>Published date <input v-model="form.published_date" type="date" /></label
      ><label>Translations JSON <textarea v-model="translationsJson" /></label
      ><button type="submit">{{ editingId ? 'Update' : 'Create' }}</button>
    </form>
    <table>
      <thead>
        <tr>
          <th>Slug</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="String(item.id)">
          <td>{{ item.slug }}</td>
          <td>{{ item.status }}</td>
          <td>
            <button type="button" @click="edit(item)">edit</button
            ><button type="button" @click="archive(item.id)">archive</button>
          </td>
        </tr>
      </tbody>
    </table>
  </main>
</template>
