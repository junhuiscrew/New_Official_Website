<!-- 页面用途：Company Trust 与 Media/Download 管理入口，所有页面全局 noindex。 -->
<script setup lang="ts">
useHead({ title: 'Company Trust', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
</script>
<template>
  <main class="admin-shell">
    <h1>Company Trust</h1>
    <nav>
      <NuxtLink to="/trust/company">Company Profile</NuxtLink
      ><NuxtLink to="/trust/capabilities">Capabilities</NuxtLink
      ><NuxtLink to="/trust/equipment">Equipment</NuxtLink
      ><NuxtLink to="/trust/certificates">Certificates</NuxtLink
      ><NuxtLink to="/trust/patents">Patents</NuxtLink><NuxtLink to="/trust/honors">Honors</NuxtLink
      ><NuxtLink to="/trust/exhibitions">Exhibitions</NuxtLink
      ><NuxtLink to="/media">Media Library</NuxtLink><NuxtLink to="/downloads">Downloads</NuxtLink>
    </nav>
    <p>真实 Company Profile、能力、设备、证书、专利、荣誉和展会使用统一 Trust 生命周期。</p>
  </main>
</template>
