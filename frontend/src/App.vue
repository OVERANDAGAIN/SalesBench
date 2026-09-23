<script setup lang="ts">
import { ref } from 'vue'
const status = ref('尚未检查')
async function checkHealth() {
  status.value = '检查中…'
  try {
    const response = await fetch('/api/health')
    if (!response.ok) throw new Error('HTTP ' + response.status)
    const data: { status: string; scope: string } = await response.json()
    status.value = `${data.status} · ${data.scope}`
  } catch { status.value = 'API 未连接；未切换为模拟成功' }
}
</script>

<template>
  <main>
    <h1>SalesBench</h1>
    <p>总工程基础入口 · 买方界面将在阶段 4A 迁移。</p>
    <button @click="checkHealth">检查 API 进程</button>
    <p role="status">{{ status }}</p>
    <p>此检查不代表数据库、身份系统或实验平台已就绪。</p>
  </main>
</template>

<style>
body { margin: 0; font-family: system-ui, sans-serif; background: #f7f8fb; color: #172035; }
main { max-width: 720px; margin: 80px auto; padding: 32px; }
button { padding: 12px 20px; border: 0; border-radius: 8px; background: #2b50df; color: white; cursor: pointer; }
</style>
