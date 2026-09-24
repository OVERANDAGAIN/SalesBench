<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import App from './App.vue'
import SellerPage from './pages/SellerPage.vue'
import WavePanel from './components/WavePanel.vue'
import { MarketClient } from './platform/client'
import { createNetworkBuyerService } from './platform/buyer'
import type { Binding } from './platform/types'
const client = shallowRef<MarketClient | null>(null)
const buyer = computed(() => client.value ? createNetworkBuyerService(client.value) : null)
const session = ref(''), token = ref(''), error = ref(''), busy = ref(false)
async function connect(binding: Binding) {
  if (busy.value) return
  busy.value = true; error.value = ''
  let candidate: MarketClient | undefined
  try {
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(binding.session_id) || typeof binding.actor_token !== 'string' || !binding.actor_token || binding.actor_token.length > 512) throw new Error('请输入有效 session 和 actor token。')
    candidate = new MarketClient(binding, sessionStorage)
    await candidate.start()
    if (!candidate.state.online) throw new Error(candidate.state.error)
    sessionStorage.setItem('sb.market.binding', JSON.stringify(binding))
    token.value = ''; client.value = candidate
  } catch (cause) { candidate?.dispose(); error.value = cause instanceof Error ? cause.message : '绑定失败' }
  finally { busy.value = false }
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement; const file = input.files?.[0]
  try { if (!file || file.size > 8192) throw new Error('请选择本机生成的角色 JSON 文件。'); await connect(JSON.parse(await file.text())) }
  catch { error.value = '角色文件无法读取；请使用 create-manual 生成的 JSON。' }
  input.value = ''
}
function logout() { client.value?.dispose(); client.value = null; sessionStorage.removeItem('sb.market.binding'); sessionStorage.removeItem('sb.market.intent'); token.value = ''; error.value = '' }
onMounted(() => { try { const saved = sessionStorage.getItem('sb.market.binding'); if (saved) void connect(JSON.parse(saved)) } catch { error.value = '当前标签页凭据无法读取，请重新绑定。' } })
onUnmounted(() => client.value?.dispose())
</script>
<template>
  <div v-if="!client" class="binding-shell"><section class="panel binding-card"><div class="eyebrow">SalesBench · 真实共享市场</div><h1>绑定本场角色</h1><p>每个标签页独立扮演一个 Buyer 或 Seller；身份由服务端凭据确认。</p><label class="binding-file">导入本地角色文件<input type="file" accept="application/json,.json" aria-label="导入角色文件" :disabled="busy" @change="importFile" /></label><div class="binding-divider">或手工输入</div><form class="seller-form" @submit.prevent="connect({ session_id: session.trim(), actor_token: token.trim() })"><label>Session ID<input v-model="session" aria-label="Session ID" autocomplete="off" required /></label><label>Actor token<input v-model="token" aria-label="Actor token" type="password" autocomplete="off" required /></label><button class="btn primary" :disabled="busy">{{ busy ? '连接中…' : '连接真实市场' }}</button></form><p v-if="error" class="field-error" role="alert">{{ error }}</p><p class="tiny">凭据仅保存在本标签页 sessionStorage，不放入 URL。刷新保留绑定；切换绑定会清除本地凭据与草稿。网络故障不会进入本地演示。</p></section></div>
  <SellerPage v-else-if="client.role === 'seller'" :client="client" @logout="logout" />
  <App v-else-if="buyer" :service="buyer" :demo-mode="false"><template #market><WavePanel :client="client" @logout="logout" /></template></App>
</template>
