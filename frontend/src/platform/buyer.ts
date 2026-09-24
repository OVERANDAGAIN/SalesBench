import type { Action, BuyerService, Message, Observation, Order, Product } from '../domain/types'
import type { BatchReceipt, ListingView, MarketAction, MarketMessage, MarketObservation } from './types'
import { MarketClient } from './client'

export function product(view: ListingView): Product {
  return { id: view.listing.id, merchantId: view.seller.id, name: view.product.name, variant: view.listing.id,
    category: '市场商品', priceCents: view.listing.unit_price_cents, stock: view.available_quantity,
    imageUrl: '/product-placeholder.svg', description: view.listing.description,
    specs: [`报价 v${view.listing.offer_revision}`, `内容 v${view.listing.content_revision}`],
    offerRevision: view.listing.offer_revision, contentRevision: view.listing.content_revision }
}
function message(row: MarketMessage, raw: MarketObservation): Message {
  const seller = raw.state.public.sellers.find(s => s.id === row.author_id)
  return { id: row.id, merchantId: row.seller_id, channel: row.channel, text: row.text, isPreset: false,
    createdAt: `step:${row.step}`, author: { id: row.author_id, name: seller?.name ?? (row.author_id === raw.actor_id ? raw.state.own.actor.name : row.author_id), role: seller ? 'merchant' : 'buyer' } }
}
export function mapBuyer(raw: MarketObservation, query: Parameters<BuyerService['observe']>[0]): Observation {
  const products = raw.state.public.listings.map(product)
  const merchants = raw.state.public.sellers.map(s => {
    const listing = products.find(p => p.merchantId === s.id)
    return { ...s, initial: s.name.slice(0, 1), color: '#dce7df', tag: '实验商家', description: listing?.description ?? '暂未上架', pitch: listing?.description ?? '暂未发布销售描述', featuredProductId: listing?.id ?? '' }
  })
  const base = { ok: true as const, schemaVersion: 'sb-platform-v1' as const, mode: 'network' as const,
    sessionId: raw.session_id, revision: raw.published_version,
    actor: { ...raw.state.own.actor, balanceCents: raw.state.own.account.balance_cents }, merchants }
  if (query.view === 'leaderboard') return { ...base, view: query.view, leaderboardSnapshot: raw.leaderboard,
    leaderboard: raw.leaderboard ? raw.leaderboard.rows.map(row => ({ ...merchants.find(m => m.id === row.seller_id)!,
      name: row.display_name, rank: row.current_rank, previousRank: row.previous_rank, profitCents: row.dev_profit_cents,
      revenueCents: null, sold: null })) : merchants.map(m => ({ ...m, rank: null, revenueCents: null, sold: null })) }
  if (query.view === 'products') return { ...base, view: query.view, products: products.filter(p => !query.merchantId || p.merchantId === query.merchantId) }
  if (query.view === 'product') {
    const selected = products.find(p => p.id === query.productId)
    if (!selected) throw new Error('该 Listing 当前未在公开市场中发布。')
    return { ...base, view: query.view, product: selected }
  }
  if (query.view === 'me') {
    const orders: Order[] = raw.state.own.orders.map(o => ({ id: o.id, productId: o.listing_id,
      productName: products.find(p => p.id === o.listing_id)?.name ?? raw.state.own.products.find(p => p.id === o.product_id)?.name ?? o.product_id,
      variant: o.listing_id, merchantId: o.seller_id, merchantName: merchants.find(m => m.id === o.seller_id)?.name ?? o.seller_id,
      quantity: o.quantity, totalCents: o.total_cents, unitPriceCents: o.unit_price_cents, createdAt: `step:${o.step}`, status: 'completed' }))
    return { ...base, view: query.view, orders, account: { initialBalanceCents: null, spentCents: orders.reduce((n, o) => n + o.totalCents, 0) } }
  }
  if (!('merchantId' in query)) throw new Error('不支持的观察页面。')
  const selected = merchants.find(m => m.id === query.merchantId) ?? merchants[0]
  if (!selected) throw new Error('当前场次没有商家。')
  const source = query.view === 'public' ? raw.state.public.messages : raw.state.inbox.messages
  const messages = source.filter(m => m.seller_id === selected.id).map(m => message(m, raw))
  const common = { ...base, merchantId: selected.id, products: products.filter(p => p.merchantId === selected.id), messages }
  if (query.view === 'public') return { ...common, view: 'public' }
  return { ...common, view: 'private', conversations: merchants.flatMap(m => {
    const last = raw.state.inbox.messages.filter(row => row.seller_id === m.id).at(-1)
    return last ? [{ merchantId: m.id, lastMessage: message(last, raw) }] : []
  }) }
}
export function marketAction(action: Action): MarketAction {
  if (action.type === 'purchase') {
    if (action.payload.expectedOfferRevision === undefined) throw new Error('缺少已观察的 offer_revision。')
    return { type: 'purchase', listing_id: action.payload.productId, quantity: action.payload.quantity,
      expected_unit_price_cents: action.payload.expectedUnitPriceCents, expected_offer_revision: action.payload.expectedOfferRevision }
  }
  return action.type === 'send_public' ? { type: action.type, seller_id: action.payload.merchantId, text: action.payload.text }
    : { type: action.type, recipient_id: action.payload.merchantId, text: action.payload.text }
}
export interface NetworkBuyerService extends Pick<BuyerService, 'observe' | 'subscribe'> {
  stage(action: Action): void
  decline(): void
  submitBatch(): Promise<BatchReceipt | null>
  getReceipt(requestId: string): Promise<BatchReceipt>
}
export function createNetworkBuyerService(client: MarketClient): NetworkBuyerService {
  return {
    async observe(query) {
      if (!client.state.observation) await client.refresh()
      if (!client.state.online || !client.state.observation) throw new Error(client.state.error || '市场未连接')
      if (client.role !== 'buyer') throw new Error('该 Buyer 页面需要 Buyer 身份。')
      return mapBuyer(client.state.observation, query)
    },
    stage(action) { client.stage(marketAction(action)) },
    decline() { client.decline() },
    // The network contract explicitly separates local composition from submission.
    async submitBatch() { await client.submit(); return client.state.lastReceipt },
    getReceipt(requestId) { return client.getReceipt(requestId) },
    subscribe(listener) { return client.subscribe(() => { if (client.state.observation) listener({ sessionId: client.state.observation.session_id,
      revision: client.state.observation.published_version, topics: ['leaderboard', 'products', 'account', 'orders', 'messages'] }) }) },
  }
}
