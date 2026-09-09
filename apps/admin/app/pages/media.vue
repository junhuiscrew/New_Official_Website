<!-- 页面用途：公开媒体资源库，以可读文件名维护上传、预览和双语元数据。 -->
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
            {{ item.type }} · {{ item.filename }}
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
    <section class="media-library-grid">
      <article v-for="item in items" :key="String(item.id)">
        <img
          v-if="item.type === 'image'"
          :src="String(item.url)"
          :alt="String(item.filename)"
          loading="lazy"
        />
        <video v-else-if="item.type === 'video'" controls preload="none">
          <source :src="String(item.url)" :type="String(item.mime_type)" />
        </video>
        <div v-else class="media-library-file">{{ item.file_extension }}</div>
        <div>
          <strong>{{ item.filename }}</strong>
          <span>{{ item.type }} · {{ item.visibility }}</span>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.admin-shell {
  display: grid;
  align-content: start;
  gap: 1rem;
}
.admin-shell > form {
  padding: 1rem;
  display: grid;
  gap: 0.8rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.8rem;
}
.media-library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: 1rem;
}
.media-library-grid article {
  min-width: 0;
  overflow: hidden;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.75rem;
}
.media-library-grid img,
.media-library-grid video,
.media-library-file {
  width: 100%;
  aspect-ratio: 4 / 3;
  display: grid;
  place-items: center;
  object-fit: cover;
  color: #75bce9;
  background: #07192c;
}
.media-library-grid article > div:last-child {
  padding: 0.75rem;
  display: grid;
  gap: 0.3rem;
}
.media-library-grid strong {
  overflow: hidden;
  color: #23394e;
  font-size: 0.76rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.media-library-grid span {
  color: #78899a;
  font-size: 0.68rem;
}
</style>
