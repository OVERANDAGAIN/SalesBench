<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { MarketClient } from '../platform/client'
import type { MarketAction } from '../platform/types'
import { amount, rankChange } from '../domain/format'
import WavePanel from '../components/WavePanel.vue'
import LeaderboardContext from '../components/LeaderboardContext.vue'
const props = defineProps<{ client: MarketClient }>()
defineEmits<{ logout: [] }>()
const observation = computed(() => props.client.state.observation!)
const own = computed(() => observation.value.state.own)
const form = reactive({ type: 'procure', offer: 'cups', product: 'cup', listing: 'cup', quantity: 1, price: 300, description: '', text: '', recipient: 'buyer-1', active: 'true' })
const error = ref('')
const options = computed(() => {
  const allowed = observation.value.opportunity?.wave.allowed_actions ?? []
  return [{ value: 'procure', label: '采购', type: 'procure' }, { value: 'create_listing', label: '建立 Listing', type: 'create_listing' },
    { value: 'price', label: '调整价格', type: 'update_listing' }, { value: 'description', label: '更新销售描述', type: 'update_listing' }, { value: 'active', label: '上架 / 下架', type: 'update_listing' },
    { value: 'send_public', label: '公开发言 / 回复', type: 'send_public' }, { value: 'send_private', label: '私人回复', type: 'send_private' }].filter(o => allowed.includes(o.type))
})
watch(options, choices => { if (!choices.some(o => o.value === form.type)) form.type = choices[0]?.value ?? '' }, { immediate: true })
function add() {
  error.value = ''
  try {
    const listingId = form.listing.includes('/') ? form.listing : `${observation.value.actor_id}/${form.listing}`
    let action: MarketAction
    switch (form.type) {
      case 'procure': {
        const offer = observation.value.opportunity?.procurement?.offers.find(o => o.id === form.offer)
        if (!offer) throw new Error('请选择当前采购观察中的报价。')
        action = { type: 'procure', offer_id: offer.id, quantity: Number(form.quantity), expected_unit_cost_cents: offer.unit_cost_cents }; break
      }
      case 'create_listing': action = { type: form.type, listing_id: listingId, product_id: form.product, unit_price_cents: Number(form.price), description: form.description }; break
      case 'price': action = { type: 'update_listing', listing_id: listingId, unit_price_cents: Number(form.price) }; break
      case 'description': action = { type: 'update_listing', listing_id: listingId, description: form.description }; break
      case 'active': action = { type: 'update_listing', listing_id: listingId, active: form.active === 'true' }; break
      case 'send_public': action = { type: form.type, seller_id: observation.value.actor_id, text: form.text }; break
      case 'send_private': action = { type: form.type, recipient_id: form.recipient, text: form.text }; break
      default: throw new Error('请选择一个本机会允许的动作。')
    }
    props.client.stage(action)
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '无法加入批次' }
}
</script>
<template>
  <main class="seller-shell">
    <header class="seller-header"><div><div class="eyebrow">SalesBench · 工程验收</div><h1>Seller 操作台</h1><p>真实 Platform → Runner → Engine → PostgreSQL · 非正式经营后台</p></div><strong data-testid="seller-balance">{{ own.actor.name }} · ¥{{ amount(own.account.balance_cents) }}</strong></header>
    <WavePanel :client="client" @logout="$emit('logout')" />
    <section class="panel seller-section"><h2>公开利润排行榜</h2><LeaderboardContext :snapshot="observation.leaderboard" /><div class="table-wrap"><table data-testid="leaderboard-table"><thead><tr><th>排名</th><th>Seller</th><th>利润（开发口径）</th><th>排名变化</th></tr></thead><tbody><tr v-for="row in observation.leaderboard?.rows ?? []" :key="row.seller_id" :data-seller-id="row.seller_id"><td>{{ row.current_rank }}</td><td>{{ row.display_name }}</td><td>¥ {{ amount(row.dev_profit_cents) }}</td><td>{{ rankChange(row.current_rank, row.previous_rank) }}</td></tr></tbody></table></div></section>
    <div class="seller-grid">
      <section class="panel seller-section"><h2>构造本轮动作</h2><form class="seller-form" @submit.prevent="add">
        <label>动作类型<select v-model="form.type" aria-label="Seller 动作类型"><option disabled value="">请选择</option><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select></label>
        <template v-if="form.type === 'procure'"><label>供应商报价<select v-model="form.offer" aria-label="采购报价"><option v-for="offer in observation.opportunity?.procurement?.offers || []" :key="offer.id" :value="offer.id">{{ offer.id }} · {{ offer.product_id }} · {{ offer.unit_cost_cents }} 分 / 件 · 供给 {{ offer.available_quantity }}</option></select></label><label>采购数量<input v-model.number="form.quantity" aria-label="采购数量" type="number" step="1" min="1" required /></label></template>
        <template v-if="['create_listing','price','description','active'].includes(form.type)"><label>Listing ID（简写自动加本人前缀）<input v-model="form.listing" aria-label="Listing ID" required /></label></template>
        <label v-if="form.type === 'create_listing'">Product ID<input v-model="form.product" aria-label="Product ID" required /></label>
        <label v-if="['create_listing','price'].includes(form.type)">售价（整数分）<input v-model.number="form.price" aria-label="售价（整数分）" type="number" min="0" step="1" required /></label>
        <label v-if="['create_listing','description'].includes(form.type)">销售描述<textarea v-model="form.description" aria-label="销售描述" maxlength="2000" required /></label>
        <label v-if="form.type === 'active'">在售状态<select v-model="form.active" aria-label="在售状态"><option value="true">active · 在售</option><option value="false">inactive · 下架</option></select></label>
        <label v-if="form.type === 'send_private'">Buyer ID<input v-model="form.recipient" aria-label="私人消息接收者" required /></label>
        <label v-if="form.type.startsWith('send_')">消息<textarea v-model="form.text" aria-label="Seller 消息内容" maxlength="500" required /></label>
        <button class="btn" :disabled="!client.editable || !options.some(o => o.value === form.type)">加入有序批次</button><p v-if="error" class="field-error" role="alert">{{ error }}</p>
      </form><p class="tiny">加入草稿不扣款、不改变库存。整批提交后以服务端回执为准。</p></section>
      <section class="panel seller-section"><h2>本人库存</h2><ul><li v-for="i in own.inventory" :key="i.product_id">{{ i.product_id }}：{{ i.quantity }} 件</li></ul><p v-if="!own.inventory.length">暂无库存；请在采购机会提交采购。</p><h2>自己的 Listings</h2><div class="table-wrap"><table><thead><tr><th>Listing / 描述</th><th>价格</th><th>数量 / 状态</th><th>版本</th></tr></thead><tbody><tr v-for="v in own.listings" :key="v.listing.id"><td>{{ v.listing.id }}<small>{{ v.listing.description }}</small></td><td>{{ v.listing.unit_price_cents }} 分</td><td>{{ v.available_quantity }} / {{ v.listing.active ? 'active' : 'inactive' }}</td><td>offer {{ v.listing.offer_revision }} / content {{ v.listing.content_revision }}</td></tr></tbody></table></div><h2>本人订单 / 销售结果</h2><div class="table-wrap"><table><thead><tr><th>订单 / Buyer</th><th>Listing</th><th>数量 / 成交</th><th>时间</th></tr></thead><tbody><tr v-for="o in own.orders" :key="o.id"><td>{{ o.id }} / {{ o.buyer_id }}</td><td>{{ o.listing_id }}</td><td>{{ o.quantity }} / {{ o.total_cents }} 分</td><td>Step {{ o.step }}</td></tr></tbody></table></div></section>
    </div>
    <section class="panel seller-section"><h2>公共市场</h2><div class="table-wrap"><table><thead><tr><th>商家 / Listing</th><th>商品 / 销售描述</th><th>价格 / 库存</th><th>版本</th></tr></thead><tbody><tr v-for="v in observation.state.public.listings" :key="v.listing.id"><td>{{ v.seller.name }} / {{ v.listing.id }}</td><td>{{ v.product.name }} · {{ v.listing.description }}</td><td>{{ v.listing.unit_price_cents }} 分 / {{ v.available_quantity }} 件</td><td>offer {{ v.listing.offer_revision }} / content {{ v.listing.content_revision }}</td></tr></tbody></table></div></section>
    <div class="seller-grid"><section class="panel seller-section"><h2>公共讨论</h2><ul class="seller-messages"><li v-for="m in observation.state.public.messages" :key="m.id"><small>{{ m.seller_id }} 频道 · {{ m.author_id }} · Step {{ m.step }}</small><p>{{ m.text }}</p></li></ul></section><section class="panel seller-section"><h2>本人 Buyer 私聊</h2><p class="tiny">仅本人会话，不显示其他 Seller 私聊。</p><ul class="seller-messages"><li v-for="m in observation.state.inbox.messages" :key="m.id"><small>{{ observation.state.inbox.conversations.find(c => c.id === m.conversation_id)?.buyer_id }} · {{ m.author_id }} · Step {{ m.step }}</small><p>{{ m.text }}</p></li></ul></section></div>
  </main>
</template>
