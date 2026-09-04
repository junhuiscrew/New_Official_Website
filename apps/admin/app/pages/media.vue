<!-- 页面用途：公开 Media Library 最小列表，私有 RFQ 文件不通过 media.read 暴露。 -->
<script setup lang="ts">
useHead({ title: 'Media Library', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const api = useAuthorityApi()
const items = ref<Array<Record<string, unknown>>>([])
const locales = ref<Array<{ id: string; native_name: string }>>([])
const selectedAsset = ref('')
const selectedLocale = ref('')
const file = ref<File | null>(null)
const translations = reactive({ alt_text: '', title: '', caption: '' })
async function load() {
  items.value = await api.detail('/media')
  locales.value = await api.detail('/locales')
}
async function upload() {
  if (!file.value) return
  const body = new FormData()
  body.append('file', file.value)
  body.append('visibility', 'public')
  await api.upload('/media/assets', body)
  file.value = null
  await load()
}
async function saveTranslation() {
  if (!selectedAsset.value || !selectedLocale.value) return
  const body = new FormData()
  body.append('alt_text', translations.alt_text)
  body.append('title', translations.title)
  body.append('caption', translations.caption)
  await api.request(`/media/${selectedAsset.value}/translations/${selectedLocale.value}`, {
    method: 'PATCH',
    body,
  })
}
onMounted(load)
</script>
<template>
  <main class="admin-shell">
    <h1>Media Library</h1>
    <form @submit.prevent="upload">
      <label
        >Public file
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf,video/mp4,video/webm"
          @change="file = ($event.target as HTMLInputElement).files?.[0] || null" /></label
      ><button type="submit">Upload to public-media</button>
    </form>
    <form @submit.prevent="saveTranslation">
      <h2>Localized metadata</h2>
      <label
        >Asset
        <select v-model="selectedAsset">
          <option v-for="item in items" :key="String(item.id)" :value="String(item.id)">
            {{ item.file_extension }} · {{ item.id }}
          </option>
        </select></label
      ><label
        >Locale
        <select v-model="selectedLocale">
          <option v-for="locale in locales" :key="locale.id" :value="locale.id">
            {{ locale.native_name }}
          </option>
        </select></label
      ><label>Alt text <input v-model="translations.alt_text" /></label
      ><label>Title <input v-model="translations.title" /></label
      ><label>Caption <textarea v-model="translations.caption" /></label
      ><button type="submit">Save metadata</button>
    </form>
    <ul>
      <li v-for="item in items" :key="String(item.id)">
        {{ item.type }} · {{ item.visibility }} · {{ item.file_extension }}
      </li>
    </ul>
  </main>
</template>
