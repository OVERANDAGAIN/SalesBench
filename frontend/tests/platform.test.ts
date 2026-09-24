import { describe, expect, it } from 'vitest'
import { MarketClient } from '../src/platform/client'
import { mapBuyer, marketAction } from '../src/platform/buyer'
import type { BatchReceipt, BatchRequest, MarketObservation } from '../src/platform/types'

function fixture() {
  const own = { actor: { id: 'buyer-1', name: 'Buyer 1' }, account: { actor_id: 'buyer-1', balance_cents: 2000 }, products: [], inventory: [], listings: [], offers: [], orders: [], messages: [], conversations: [] }
  const publicState = { version: 2, time: { step: 0 }, sellers: [{ id: 'seller-a', name: 'Seller A' }], listings: [{ listing: { id: 'seller-a/cup', seller_id: 'seller-a', product_id: 'cup', unit_price_cents: 300, description: 'Published', active: true, offer_revision: 3, content_revision: 2 }, product: { id: 'cup', name: 'Cup' }, seller: { id: 'seller-a', name: 'Seller A' }, available_quantity: 1 }], messages: [] }
  const state = { public: publicState, own, inbox: { ...own, messages: [{ id: 'private-1', channel: 'private' as const, author_id: 'seller-a', seller_id: 'seller-a', text: 'private text', step: 0, conversation_id: 'conversation' }] } }
  const wave = { name: 'BUYER_ACTION', role: 'buyer' as const, allowed_actions: ['send_public', 'send_private', 'purchase', 'wait'], max_actions: 3, max_messages: 2, max_purchases: 1 }
  const context = { round: 1, tick: 1, wave: 'BUYER_ACTION' }
  const observation: MarketObservation = { schema_version: 'sb-platform-v1', session_id: 'test-market', actor_id: 'buyer-1', published_version: 2, state,
    opportunity: { opportunity_id: 'a'.repeat(64), context, state, wave, procurement: null }, runtime: { status: 'awaiting_batches', runner_phase: 'publishing', published_version: 2, engine_step: 0, next_boundary: { context, wave } } }
  const saved = new Map<string, string>()
  const storage = { getItem: (key: string) => saved.get(key) ?? null, setItem: (key: string, value: string) => { saved.set(key, value) }, removeItem: (key: string) => { saved.delete(key) } }
  const requests: BatchRequest[] = []
  let receipt: BatchReceipt | null = null
  let offline = false, loseAcknowledgement = false, reject = false
  const fetcher: typeof fetch = async (url, init) => {
    if (offline) throw new TypeError('offline')
    const path = String(url)
    if (init?.method === 'POST') {
      const body: BatchRequest = JSON.parse(String(init.body)); requests.push(body)
      receipt = { session_id: 'test-market', actor_id: 'buyer-1', request_id: body.request_id, opportunity_id: body.opportunity_id,
        status: reject ? 'rejected' : 'pending', code: reject ? 'STALE_OBSERVATION' : null, submitted_version: body.observation_version, published_version: 2, outcomes: [] }
      if (loseAcknowledgement) throw new TypeError('ack lost')
      return Response.json(receipt, { status: reject ? 409 : 202 })
    }
    if (path.endsWith('/observation')) return Response.json(observation)
    if (path.endsWith('/receipts')) return Response.json({ receipts: receipt ? [receipt] : [] })
    if (path.includes('/receipts/')) return receipt ? Response.json(receipt) : Response.json({ error: { code: 'RECEIPT_NOT_FOUND' } }, { status: 404 })
    return Response.json({ notices: [] })
  }
  const make = () => new MarketClient({ session_id: 'test-market', actor_token: 'not-a-real-token' }, storage, fetcher)
  return { observation, requests, make, offline: () => { offline = true }, ackLost: () => { loseAcknowledgement = true }, reject: () => { reject = true } }
}
const purchase = { type: 'purchase' as const, listing_id: 'seller-a/cup', quantity: 1, expected_unit_price_cents: 300, expected_offer_revision: 3 }

describe('real platform transport and opportunity composition', () => {
  it('maps only authorized information, Listing versions and logical time', () => {
    const { observation } = fixture()
    const products = mapBuyer(observation, { view: 'products' })
    expect(products.mode).toBe('network')
    expect(products.view === 'products' && products.products[0]?.offerRevision).toBe(3)
    expect(JSON.stringify(products)).not.toContain('private text')
    const ranking = mapBuyer(observation, { view: 'leaderboard' })
    expect(ranking.view === 'leaderboard' && ranking.leaderboard[0]?.revenueCents).toBeNull()
    const privateView = mapBuyer(observation, { view: 'private', merchantId: 'seller-a' })
    expect(privateView.view === 'private' && privateView.messages[0]?.createdAt).toBe('step:0')
    expect(() => marketAction({ id: 'id', type: 'purchase', payload: { productId: 'seller-a/cup', quantity: 1, expectedUnitPriceCents: 300 } })).toThrow('offer_revision')
  })
  it('collects ordered messages then purchase; nothing executes before explicit submit', async () => {
    const f = fixture(), c = f.make(); await c.refresh()
    c.stage(purchase); c.stage({ type: 'send_public', seller_id: 'seller-a', text: 'public' }); c.stage({ type: 'send_private', recipient_id: 'seller-a', text: 'private' })
    expect(f.requests).toHaveLength(0)
    expect(c.state.draft.map(a => a.type)).toEqual(['send_public', 'send_private', 'purchase'])
    expect(() => c.stage({ type: 'wait' })).toThrow()
    await c.submit()
    expect(f.requests).toHaveLength(1)
    expect(c.state.lastReceipt?.status).toBe('pending')
    expect(c.editable).toBe(false)
    expect(c.state.observation?.state.own.account.balance_cents).toBe(2000)
  })
  it('does not reinterpret unsubmitted input as Wait; explicit decline retains messages', async () => {
    const f = fixture(), c = f.make(); await c.refresh(); await c.refresh()
    expect(f.requests).toHaveLength(0)
    c.stage({ type: 'send_public', seller_id: 'seller-a', text: 'question' }); c.stage(purchase); c.decline()
    expect(c.state.draft.map(a => a.type)).toEqual(['send_public'])
    c.clear(); c.decline(); expect(c.state.draft).toEqual([{ type: 'wait' }])
  })
  it('keeps old observation and quote revision in stale draft instead of silently rebasing', async () => {
    const f = fixture(), c = f.make(); await c.refresh(); c.stage(purchase)
    f.observation.published_version = 4; f.observation.state.public.listings[0]!.listing.unit_price_cents = 400
    await c.refresh(); expect(c.staleDraft).toBe(true)
    await expect(c.submit()).rejects.toThrow('观察版本')
    expect(c.state.draft[0]).toEqual(purchase); expect(f.requests).toHaveLength(0)
  })
  it('recovers lost acknowledgement and browser refresh using the original durable request', async () => {
    const f = fixture(), c = f.make(); await c.refresh(); c.stage(purchase); f.ackLost(); await c.submit()
    const original = c.state.lastRequest!.request_id
    const restarted = f.make(); await restarted.refresh(); await restarted.retry()
    expect(restarted.state.lastRequest?.request_id).toBe(original)
    expect(restarted.state.lastReceipt?.status).toBe('pending')
    expect(f.requests).toHaveLength(1)
  })
  it('keeps network failure explicit and preserves uncertain request across refresh', async () => {
    const f = fixture(), c = f.make(); await c.refresh(); c.stage(purchase); f.offline(); await c.submit()
    expect(c.state.online).toBe(false); expect(c.state.unknown).toBe(true)
    expect(c.state.error).toContain('未切换为本地演示')
    expect(c.state.lastRequest?.actions).toEqual([purchase])
    expect(f.requests).toHaveLength(0)
  })
  it('shows a durable rejected receipt without fabricating an order or changing balances', async () => {
    const f = fixture(), c = f.make(); await c.refresh(); c.stage(purchase); f.reject(); await c.submit()
    expect(c.state.lastReceipt?.status).toBe('rejected')
    expect(c.state.lastReceipt?.code).toBe('STALE_OBSERVATION')
    expect(c.state.observation?.state.own.orders).toEqual([])
  })
  it('acknowledged current receipt locks editing even if an older receipt poll is still in flight', async () => {
    const f = fixture(), c = f.make(); await c.refresh(); c.stage(purchase); await c.submit()
    c.state.receipts = [] // A poll started before submit can still return an older list.
    expect(c.submitted?.status).toBe('pending')
    expect(c.editable).toBe(false)
    expect(() => c.stage(purchase)).toThrow()
  })
})
