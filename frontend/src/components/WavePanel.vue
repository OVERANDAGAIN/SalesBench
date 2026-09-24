<script setup lang="ts">
import { computed, ref } from 'vue'
import { actionLabel, explain, MarketClient } from '../platform/client'
const props = defineProps<{ client: MarketClient }>()
defineEmits<{ logout: [] }>()
const s = props.client.state
const localError = ref('')
const context = computed(() => s.observation?.runtime.next_boundary?.context)
const wave = computed(() => s.observation?.opportunity?.wave)
const names: Record<string, string> = { ROUND_PROCUREMENT: 'Round 采购', SELLER_STRATEGY: 'Seller 策略', BUYER_ACTION: 'Buyer 行动' }
async function perform(work: () => unknown) { localError.value = ''; try { await work() } catch (error) { localError.value = error instanceof Error ? error.message : '操作失败' } }
</script>
<template>
  <section class="panel wave-panel" aria-label="市场运行与本轮批次" data-testid="wave-panel">
    <div class="wave-title"><strong>真实共享市场 · {{ s.observation?.state.own.actor.name }}</strong><span class="tiny">{{ s.observation?.session_id }}</span><button class="text-btn" @click="$emit('logout')">切换绑定</button></div>
    <div class="wave-facts"><span data-testid="wave">{{ context ? `Round ${context.round} / Tick ${context.tick} / ${names[context.wave] || context.wave}` : s.observation?.runtime.status === 'completed' ? '场次已完成' : '场次已停止' }}</span><span data-testid="publication">Publication {{ s.observation?.published_version }}</span><span>Step {{ s.observation?.runtime.engine_step }}</span><span>{{ s.online ? '服务已连接' : '连接中断 · 数据可能过期' }}</span></div>
    <p v-if="s.unknown" class="field-error" role="alert">提交结果未知。草稿已锁定；请查询原回执或重试原请求，不能另建购买请求。</p>
    <p v-else-if="client.submitted" class="wave-wait" role="status">本人已提交 · {{ client.submitted.status }} · 等待其他参与者完成本 Wave。</p>
    <p v-else-if="s.observation?.opportunity" class="wave-wait">本人有行动机会，尚未提交。草稿不会自动执行；未提交不等于 Wait。</p>
    <p v-else class="wave-wait">本人当前无行动机会。{{ s.observation?.runtime.status === 'completed' ? '可继续查询已提交结果。' : s.observation?.runtime.status === 'failed' ? '场次发生技术故障，请查看回执。' : '等待其他参与者完成本 Wave。' }}</p>
    <p v-if="wave" class="tiny">本机会 {{ s.observation?.opportunity?.opportunity_id.slice(0, 12) }} · 最多 {{ wave.max_actions }} 个动作 / {{ wave.max_messages }} 条消息 / {{ wave.max_purchases }} 笔末尾购买</p>
    <p v-if="client.staleDraft" class="field-error" role="alert">草稿基于旧 publication {{ s.anchor?.version }}，没有自动替换报价。请检查新观察后清除并重新决定。</p>
    <ol v-if="s.draft.length" class="batch-list" aria-label="本轮有序草稿"><li v-for="(action, i) in s.draft" :key="i"><span>{{ actionLabel(action) }}</span><span class="batch-controls"><button class="text-btn" :disabled="!client.editable || client.staleDraft" :aria-label="`上移第 ${i + 1} 个动作`" @click="client.move(i, -1)">↑</button><button class="text-btn" :disabled="!client.editable || client.staleDraft" :aria-label="`下移第 ${i + 1} 个动作`" @click="client.move(i, 1)">↓</button><button class="text-btn" :disabled="s.unknown || s.busy || !!client.submitted" :aria-label="`移除第 ${i + 1} 个动作`" @click="client.remove(i)">移除</button></span></li></ol>
    <div class="wave-actions"><button class="btn primary" :disabled="!client.editable || !s.draft.length || client.staleDraft" @click="perform(() => client.submit())">{{ s.busy ? '正在提交…' : '提交本轮批次' }}</button><button class="btn" :disabled="!client.editable || !!s.draft.length" @click="perform(() => client.stage({ type: 'wait' }))">明确 Wait / 不行动</button><button class="text-btn" :disabled="s.unknown || s.busy || !s.draft.length" @click="client.clear()">清除草稿</button><button class="text-btn" @click="client.refresh()">刷新服务器观察</button><button v-if="s.lastRequest" class="btn" :disabled="s.busy" @click="perform(() => client.retry())">查询 / 重试原请求</button></div>
    <p v-if="s.error || localError" class="field-error" role="alert">{{ localError || s.error }}</p>
    <div v-if="s.lastReceipt" class="receipt" data-testid="latest-receipt"><strong>本人回执：{{ s.lastReceipt.status }}</strong><span class="tiny"> {{ s.lastReceipt.request_id }} · publication {{ s.lastReceipt.published_version }}</span><p v-if="s.lastReceipt.code">{{ explain(s.lastReceipt.code) }} ({{ s.lastReceipt.code }})</p><ul><li v-for="outcome in s.lastReceipt.outcomes" :key="outcome.action_id">{{ outcome.status }} <span v-if="outcome.result">· {{ explain(outcome.result.code) }} ({{ outcome.result.code }})</span><span v-if="outcome.reason">· {{ outcome.reason }}</span></li></ul></div>
    <details v-if="s.receipts.length"><summary>本人最近回执（{{ s.receipts.length }}）</summary><ul class="receipt-history"><li v-for="r in s.receipts" :key="r.request_id">{{ r.request_id }} · {{ r.status }} · pub {{ r.published_version }}<span v-for="o in r.outcomes" :key="o.action_id"> / {{ o.result?.code || o.reason || o.status }}</span></li></ul></details>
  </section>
</template>
