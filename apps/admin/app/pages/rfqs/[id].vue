<!-- 页面用途：RFQ 真实详情、项目、私有附件、分配、状态、扫描和签名下载。 -->
<script setup lang="ts">
useHead({ title: 'RFQ Detail', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const route = useRoute()
const api = useAuthorityApi()
const detail = ref<{
  rfq: Record<string, unknown>
  items: Array<Record<string, unknown>>
  files: Array<Record<string, unknown>>
  audit_logs: Array<Record<string, unknown>>
} | null>(null)
const assigned_to = ref('')
const status = ref('')
const uploadFile = ref<File | null>(null)
const uploadItemId = ref('')
async function load() {
  const result = await api.detail<{
    rfq: Record<string, unknown>
    items: Array<Record<string, unknown>>
    files: Array<Record<string, unknown>>
    audit_logs: Array<Record<string, unknown>>
  }>(`/rfqs/${route.params.id}`)
  detail.value = result
  status.value = String(result.rfq.status)
  assigned_to.value = String(result.rfq.assigned_to || '')
}
async function assign() {
  await api.create(`/rfqs/${route.params.id}/assign`, { assigned_to: assigned_to.value || null })
  await load()
}
async function updateStatus() {
  await api.update(`/rfqs/${route.params.id}`, { status: status.value })
  await load()
}
async function download(fileId: unknown) {
  const result = await api.create<{ url: string }>(
    `/rfqs/${route.params.id}/files/${fileId}/download-url`,
    {},
  )
  window.location.assign(result.url)
}
async function upload() {
  if (!uploadFile.value) return
  const body = new FormData()
  body.append('file', uploadFile.value)
  body.append('file_category', 'other')
  if (uploadItemId.value) body.append('item_id', uploadItemId.value)
  await api.upload(`/rfqs/${route.params.id}/files`, body)
  uploadFile.value = null
  await load()
}
onMounted(load)
</script>
<template>
  <main class="admin-shell">
    <h1>RFQ {{ detail?.rfq.public_reference }}</h1>
    <label>assigned_to <input v-model="assigned_to" /></label
    ><button type="button" @click="assign">Assign</button
    ><label
      >status
      <select v-model="status">
        <option
          v-for="value in [
            'new',
            'qualified',
            'in_progress',
            'waiting_customer',
            'quoted',
            'won',
            'lost',
            'spam',
            'closed',
          ]"
          :key="value"
        >
          {{ value }}
        </option>
      </select></label
    ><button type="button" @click="updateStatus">Update status</button>
    <h2>items</h2>
    <pre>{{ detail?.items }}</pre>
    <h2>files</h2>
    <form @submit.prevent="upload">
      <input
        type="file"
        @change="uploadFile = ($event.target as HTMLInputElement).files?.[0] || null"
      /><label
        >Item
        <select v-model="uploadItemId">
          <option value="">Whole RFQ</option>
          <option
            v-for="item in detail?.items || []"
            :key="String(item.id)"
            :value="String(item.id)"
          >
            {{ item.product_name_text || item.id }}
          </option>
        </select></label
      ><button type="submit">Upload private file</button>
    </form>
    <table>
      <tbody>
        <tr v-for="file in detail?.files || []" :key="String(file.id)">
          <td>{{ file.original_filename }}</td>
          <td>{{ file.malware_scan_status }} / {{ file.upload_status }}</td>
          <td>
            <button
              type="button"
              :disabled="file.malware_scan_status !== 'clean'"
              @click="download(file.id)"
            >
              Signed download
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <h2>Audit</h2>
    <pre>{{ detail?.audit_logs }}</pre>
  </main>
</template>
