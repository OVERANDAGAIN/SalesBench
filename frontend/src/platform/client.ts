import { reactive } from 'vue'
import type { BatchReceipt, BatchRequest, Binding, MarketAction, MarketObservation } from './types'

export class PlatformError extends Error {
  constructor(public code: string) { super(explain(code)) }
}
const explanations: Record<string, string> = {
  STALE_OBSERVATION: '观察版本已过期。请检查新观察，清除旧草稿后重新决定。',
  PRICE_CHANGED: '报价已改变，本次购买未成交。', STALE_LISTING: '报价版本已过期，本次购买未成交。',
  OUT_OF_STOCK: '库存不足，本次购买未成交。', INSUFFICIENT_FUNDS: '资金不足，本次操作未完成。',
  COMMIT_UNKNOWN: '提交结果未知。请查询或用原请求重试，勿创建替代请求。',
  NETWORK_UNAVAILABLE: '无法连接市场服务。保留草稿和原请求，未切换为本地演示。',
  INVALID_ACTOR_BINDING: '场次或角色凭据无效，请重新绑定。', AUTHENTICATION_REQUIRED: '需要有效角色凭据。',
  OPPORTUNITY_ALREADY_SUBMITTED: '本机会已经提交，请查看本人回执。', OPPORTUNITY_NOT_CURRENT: '当前没有该行动机会。',
  ACTION_ID_CONFLICT: '请求 ID 与原内容冲突，请保留原请求并检查回执。', SESSION_TERMINAL: '场次已结束，不能再提交。',
}
export function explain(code: string) { return explanations[code] || code }
export function actionLabel(a: MarketAction): string {
  switch (a.type) {
    case 'wait': return 'Wait · 明确不行动'
    case 'procure': return `采购 ${a.offer_id} × ${a.quantity} · 成本 ${a.expected_unit_cost_cents} 分`
    case 'purchase': return `购买 ${a.listing_id} × ${a.quantity} · 报价 ${a.expected_unit_price_cents} 分 / v${a.expected_offer_revision}`
    case 'create_listing': return `上架 ${a.listing_id} · ${a.unit_price_cents} 分 · ${a.description}`
    case 'update_listing': return `更新 ${a.listing_id} · ${a.unit_price_cents === undefined ? '' : a.unit_price_cents + ' 分'} ${a.active === undefined ? '' : a.active ? '在售' : '下架'} ${a.description ?? ''}`
    case 'send_public': return `公开 → ${a.seller_id}：${a.text}`
    case 'send_private': return `私聊 → ${a.recipient_id}：${a.text}`
  }
}
type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
const intentKey = 'sb.market.intent'
export class MarketClient {
  readonly state = reactive({ observation: null as MarketObservation | null, receipts: [] as BatchReceipt[],
    draft: [] as MarketAction[], anchor: null as { version: number; opportunity: string } | null,
    lastRequest: null as BatchRequest | null, lastReceipt: null as BatchReceipt | null,
    unknown: false, online: false, busy: false, error: '' })
  private listeners = new Set<() => void>()
  private timer?: ReturnType<typeof setInterval>
  private refreshing?: Promise<void>
  private loaded = false
  private disposed = false
  constructor(private binding: Binding, private storage: StorageLike, private fetcher: typeof fetch = fetch) {}
  get role(): 'seller' | 'buyer' { return this.state.observation?.state.public.sellers.some(s => s.id === this.state.observation?.actor_id) ? 'seller' : 'buyer' }
  get submitted() {
    const opportunity = this.state.observation?.opportunity?.opportunity_id
    return [this.state.lastReceipt, ...this.state.receipts].find(r => r && r.opportunity_id === opportunity && r.status !== 'rejected')
  }
  get staleDraft() { return !!this.state.anchor && this.state.anchor.version !== this.state.observation?.published_version }
  get editable() { return !this.disposed && !!this.state.observation?.opportunity && this.state.online && !this.state.busy && !this.submitted && !this.state.unknown }
  subscribe(listener: () => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private notify() { if (!this.disposed) this.listeners.forEach(fn => fn()) }
  private persist() {
    if (this.disposed) return
    this.storage.setItem(intentKey, JSON.stringify({ session: this.binding.session_id, actor: this.state.observation?.actor_id,
      draft: this.state.draft, anchor: this.state.anchor, request: this.state.lastRequest, unknown: this.state.unknown }))
  }
  private async api<T>(path: string, body?: BatchRequest): Promise<T> {
    let response: Response
    try {
      // Browser fetch must not receive the MarketClient instance as its WebIDL receiver.
      const send = this.fetcher
      response = await send(`/api/v1/sessions/${encodeURIComponent(this.binding.session_id)}${path}`, {
        method: body ? 'POST' : 'GET', headers: { Authorization: `Bearer ${this.binding.actor_token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
        body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(6000), cache: 'no-store',
      })
    } catch { throw new PlatformError('NETWORK_UNAVAILABLE') }
    let payload: any
    try { payload = await response.json() } catch { throw new PlatformError(response.ok ? 'INVALID_SERVER_RESPONSE' : 'NETWORK_UNAVAILABLE') }
    // 409 admission rejection is a durable receipt, not a transport exception.
    if (!response.ok && !(response.status === 409 && payload.status === 'rejected')) throw new PlatformError(payload.error?.code || `HTTP_${response.status}`)
    return payload as T
  }
  async start() { await this.refresh(); this.timer = setInterval(() => { void this.refresh() }, 1000) }
  dispose() { this.disposed = true; clearInterval(this.timer); this.listeners.clear() }
  getReceipt(requestId: string) { return this.api<BatchReceipt>(`/receipts/${encodeURIComponent(requestId)}`) }
  async refresh(): Promise<void> {
    if (this.refreshing) return this.refreshing
    this.refreshing = this.read().finally(() => { this.refreshing = undefined })
    return this.refreshing
  }
  private async read() {
    try {
      const cursor = this.state.observation?.published_version ?? -1
      await this.api(`/notifications?after_version=${cursor}`)
      // Same-version runtime/receipts can change (pending or terminal failure).
      const observation = await this.api<MarketObservation>('/observation')
      if (observation.schema_version !== 'sb-platform-v1' || observation.session_id !== this.binding.session_id) throw new PlatformError('INVALID_SERVER_RESPONSE')
      const { receipts } = await this.api<{ receipts: BatchReceipt[] }>('/receipts')
      if (this.disposed) return
      const changed = JSON.stringify(observation) !== JSON.stringify(this.state.observation) || !this.state.online
      this.state.observation = observation
      this.state.receipts = receipts
      this.state.online = true
      this.state.error = ''
      if (!this.loaded) {
        this.loaded = true
        try {
          const saved = JSON.parse(this.storage.getItem(intentKey) || 'null')
          if (saved?.session === this.binding.session_id && saved?.actor === observation.actor_id) {
            this.state.draft = saved.draft; this.state.anchor = saved.anchor; this.state.lastRequest = saved.request; this.state.unknown = !!saved.unknown
          }
        } catch { this.state.error = '本地草稿无法读取，请清除后重新决定。' }
      }
      const known = receipts.find(r => r.request_id === this.state.lastRequest?.request_id)
      if (known) this.accept(known)
      else if (!this.state.lastRequest) this.state.lastReceipt = receipts[0] ?? null
      if (changed) this.notify()
    } catch (error) {
      if (this.disposed) return
      this.state.online = false; this.state.error = error instanceof Error ? error.message : '读取失败'
      this.notify()
    }
  }
  stage(action: MarketAction) {
    if (!this.editable) throw new Error('当前不能编辑本轮批次：请检查机会、连接和回执。')
    if (this.staleDraft) throw new PlatformError('STALE_OBSERVATION')
    const observation = this.state.observation!
    const opportunity = observation.opportunity!
    const batch = [...this.state.draft]
    // Preserve purchase-last when adding a message via the five Buyer pages.
    const purchase = batch.findIndex(a => a.type === 'purchase')
    if (purchase >= 0 && action.type.startsWith('send_')) batch.splice(purchase, 0, action)
    else batch.push(action)
    const wave = opportunity.wave
    if (batch.some(a => !wave.allowed_actions.includes(a.type)) || batch.length > wave.max_actions ||
        batch.filter(a => a.type.startsWith('send_')).length > wave.max_messages ||
        batch.filter(a => a.type === 'purchase').length > wave.max_purchases ||
        (batch.some(a => a.type === 'wait') && batch.length !== 1)) throw new Error('批次超出当前 opportunity 的动作/消息预算，或 Wait 不能与其他动作混用。')
    this.state.draft = batch
    this.state.anchor ??= { version: observation.published_version, opportunity: opportunity.opportunity_id }
    this.persist()
  }
  decline() {
    if (!this.editable || this.staleDraft) throw new Error('当前不能修改批次，请检查机会或旧草稿。')
    this.state.draft = this.state.draft.filter(a => a.type !== 'purchase')
    if (!this.state.draft.length) { this.state.anchor = null; this.stage({ type: 'wait' }) }
    this.persist()
  }
  remove(index: number) { if (!this.state.unknown && !this.state.busy && !this.submitted) { this.state.draft.splice(index, 1); if (!this.state.draft.length) this.state.anchor = null; this.persist() } }
  move(index: number, offset: number) {
    if (!this.editable || this.staleDraft) return
    const batch = [...this.state.draft]; const to = index + offset
    if (to < 0 || to >= batch.length) return
    ;[batch[index], batch[to]] = [batch[to]!, batch[index]!]
    if (batch.some((a, i) => a.type === 'purchase' && i !== batch.length - 1)) return
    this.state.draft = batch; this.persist()
  }
  clear() { if (!this.state.unknown && !this.state.busy) { this.state.draft = []; this.state.anchor = null; this.persist() } }
  private accept(receipt: BatchReceipt) {
    if (this.disposed) return
    this.state.lastReceipt = receipt; this.state.unknown = false
    if (receipt.status !== 'rejected' && this.state.anchor?.opportunity === receipt.opportunity_id) { this.state.draft = []; this.state.anchor = null }
    this.persist()
  }
  async submit() {
    if (!this.editable || !this.state.draft.length || !this.state.anchor) throw new Error('没有可以提交的本轮批次。')
    // Even stale drafts retain the original observation/revisions; no silent rebase.
    if (this.staleDraft) throw new PlatformError('STALE_OBSERVATION')
    this.state.lastRequest = { request_id: `web-${crypto.randomUUID()}`, observation_version: this.state.anchor.version,
      opportunity_id: this.state.anchor.opportunity, actions: JSON.parse(JSON.stringify(this.state.draft)) }
    return this.sendOriginal()
  }
  private async sendOriginal() {
    if (!this.state.lastRequest || this.state.busy) return
    this.state.busy = true; this.state.unknown = true; this.persist()
    try { this.accept(await this.api<BatchReceipt>('/actions', this.state.lastRequest)) }
    catch (error) { this.state.error = error instanceof Error ? error.message : '提交结果未知' }
    finally { this.state.busy = false; this.persist() }
    await this.refresh()
  }
  async retry() {
    if (!this.state.lastRequest || this.state.busy) return
    try { this.accept(await this.api<BatchReceipt>(`/receipts/${encodeURIComponent(this.state.lastRequest.request_id)}`)); await this.refresh() }
    catch (error) { if (error instanceof PlatformError && error.code === 'RECEIPT_NOT_FOUND') await this.sendOriginal(); else this.state.error = error instanceof Error ? error.message : '查询失败' }
  }
}
