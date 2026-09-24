import { computed, onMounted, onUnmounted, reactive } from 'vue'
import type { Action, ActionResult, Actor, BuyerService, Merchant, Observation, Page, Product, Query } from '../domain/types'
import type { NetworkBuyerService } from '../platform/buyer'

type Dialog = 'loading' | 'detail' | 'checkout' | 'result' | 'config' | null
export function useBuyerApp(service: BuyerService | NetworkBuyerService) {
  const state = reactive({
    page: 'leaderboard' as Page, merchantId: 's1', filterMerchantId: undefined as string | undefined,
    snapshot: null as Observation | null, actor: null as Actor | null,
    loading: false, error: '', dialog: null as Dialog, product: null as Product | null,
    merchant: null as Merchant | null, checkoutBalanceCents: 0, dialogError: '', purchasing: false, sending: false,
    purchaseError: '', messageError: '', drafts: {} as Record<string, string>, toast: '',
    result: null as Extract<ActionResult, { type: 'purchase' }> | null,
  })
  let requestSequence = 0
  let dialogSequence = 0
  let toastTimer: ReturnType<typeof setTimeout> | undefined
  let purchaseIntent: Extract<Action, { type: 'purchase' }> | undefined
  const messageIntents = new Map<string, Action>()
  const draftKey = computed(() => `${state.page}:${state.merchantId}`)
  const draft = computed(() => state.drafts[draftKey.value] || '')
  const message = (error: unknown) => error instanceof Error ? error.message : '请求失败，请稍后重试。'
  function toast(text: string) {
    state.toast = text
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { state.toast = '' }, 3500)
  }
  function query(): Query {
    if (state.page === 'public' || state.page === 'private') return { view: state.page, merchantId: state.merchantId }
    if (state.page === 'products') return state.filterMerchantId ? { view: 'products', merchantId: state.filterMerchantId } : { view: 'products' }
    return { view: state.page }
  }
  async function refresh() {
    const sequence = ++requestSequence
    state.loading = true
    state.error = ''
    try {
      const observation = await service.observe(query())
      if (sequence !== requestSequence) return
      if (!observation.ok) { state.error = observation.error.message; return }
      state.snapshot = observation
      state.actor = observation.actor
      if (observation.view === 'public' || observation.view === 'private') state.merchantId = observation.merchantId
      else if (!observation.merchants.some(m => m.id === state.merchantId)) state.merchantId = observation.merchants[0]?.id ?? ''
    } catch (error) { if (sequence === requestSequence) state.error = message(error) }
    finally { if (sequence === requestSequence) state.loading = false }
  }
  function close() {
    if (state.purchasing) return
    dialogSequence++
    state.dialog = null
    state.dialogError = ''
  }
  function navigate(page: Page, merchantId?: string) {
    if (state.purchasing) return
    close()
    state.page = page
    if (merchantId) state.merchantId = merchantId
    state.filterMerchantId = page === 'products' ? merchantId : undefined
    state.messageError = ''
    void refresh()
  }
  async function openProduct(productId: string, target: 'detail' | 'checkout' = 'detail') {
    if (state.purchasing) return
    const sequence = ++dialogSequence
    state.dialog = 'loading'
    state.dialogError = ''
    state.purchaseError = ''
    purchaseIntent = undefined
    try {
      const observation = await service.observe({ view: 'product', productId })
      if (sequence !== dialogSequence) return
      if (!observation.ok) { state.dialogError = observation.error.message; return }
      if (observation.view !== 'product') throw new Error('商品观察格式不匹配。')
      state.product = observation.product
      state.merchant = observation.merchants.find(m => m.id === observation.product.merchantId)!
      state.actor = observation.actor
      state.checkoutBalanceCents = observation.actor.balanceCents
      state.dialog = target
    } catch (error) { if (sequence === dialogSequence) state.dialogError = message(error) }
  }
  async function confirmPurchase(quantity: number) {
    if (!state.product || state.purchasing || state.dialog !== 'checkout') return
    const payload = { productId: state.product.id, quantity, expectedUnitPriceCents: state.product.priceCents, ...(state.product.offerRevision === undefined ? {} : { expectedOfferRevision: state.product.offerRevision }) }
    if (!purchaseIntent || JSON.stringify(purchaseIntent.payload) !== JSON.stringify(payload)) purchaseIntent = { id: `purchase-${crypto.randomUUID()}`, type: 'purchase', payload }
    state.purchasing = true
    state.purchaseError = ''
    try {
      if ('stage' in service) { service.stage(purchaseIntent); state.purchasing = false; close(); toast('购买已加入本轮草稿，尚未成交。请检查批次并提交本轮。'); return }
      const receipt = await service.execute(purchaseIntent)
      if (receipt.status === 'failed') { state.purchaseError = receipt.error.message; return }
      if (receipt.status === 'pending') { state.purchaseError = '操作仍在处理中，请稍后重试同一请求。'; return }
      if (receipt.result.type !== 'purchase') throw new Error('购买回执格式不匹配。')
      state.result = receipt.result
      state.toast = ''
      await refresh()
      state.dialog = 'result'
    } catch (error) { state.purchaseError = message(error) }
    finally { state.purchasing = false }
  }
  function decline() {
    try {
      if ('decline' in service) { service.decline(); close(); toast('已移除购买意图；保留消息或明确 Wait。请提交本轮。') }
      else { close(); toast('已选择暂不购买，余额不变。') }
    } catch (error) { state.purchaseError = message(error); toast(message(error)) }
  }
  function setDraft(text: string) { state.drafts[draftKey.value] = text; state.messageError = '' }
  async function send() {
    if (state.sending || state.loading || !['public', 'private'].includes(state.page)) return
    const key = draftKey.value
    const text = state.drafts[key] || ''
    if (!text.trim()) return
    const type = state.page === 'public' ? 'send_public' : 'send_private'
    const payload = { merchantId: state.merchantId, text }
    let action = messageIntents.get(key)
    if (!action || action.type !== type || JSON.stringify(action.payload) !== JSON.stringify(payload)) {
      action = { id: `message-${crypto.randomUUID()}`, type, payload }
      messageIntents.set(key, action)
    }
    state.sending = true
    state.messageError = ''
    try {
      if ('stage' in service) { service.stage(action); state.drafts[key] = ''; messageIntents.delete(key); toast('消息已加入本轮草稿，尚未发送。请提交本轮。'); return }
      const receipt = await service.execute(action)
      if (receipt.status === 'failed') { state.messageError = receipt.error.message; return }
      if (receipt.status === 'pending') { state.messageError = '消息仍在处理中，请稍后重试同一请求。'; return }
      state.drafts[key] = ''
      messageIntents.delete(key)
      toast('消息已发送，演示预设回复稍后到达。')
      await refresh()
    } catch (error) { state.messageError = message(error) }
    finally { state.sending = false }
  }
  const unsubscribe = service.subscribe(() => { void refresh() })
  onMounted(refresh)
  onUnmounted(() => { requestSequence++; dialogSequence++; unsubscribe(); clearTimeout(toastTimer) })
  return { state, draft, refresh, navigate, openProduct, close, confirmPurchase, decline, setDraft, send }
}
