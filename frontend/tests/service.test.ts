import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createDemoHost } from '../src/demo/service'
import type { Action, ChangeEvent, Query } from '../src/domain/types'
import { createAgentBoundary } from '../src/services/agent'
import { createNotConnectedService } from '../src/services/notConnected'

let host: ReturnType<typeof createDemoHost>
beforeEach(() => {
  vi.useFakeTimers()
  host = createDemoHost({ latencyMs: 10, replyDelayMs: 1000, clock: () => '2026-09-23T06:00:00.000Z' })
})
afterEach(() => { host.dispose(); vi.useRealTimers() })
const purchase = (id = 'buy-1', quantity = 1): Action => ({ id, type: 'purchase', payload: { productId: 'p1', quantity, expectedUnitPriceCents: 8900 } })
async function complete<T>(promise: Promise<T>) { await vi.advanceTimersByTimeAsync(10); return promise }
async function snapshot() {
  const buyer = host.bindBuyer('buyer_001')
  return complete(Promise.all((['products', 'leaderboard', 'me'] as const).map(view => buyer.observe({ view }))))
}

describe('identity-bound asynchronous demo service', () => {
  it('returns isolated public snapshots and image URLs, not embedded image bytes', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const first = await complete(buyer.observe({ view: 'products' }))
    if (!first.ok || first.view !== 'products') throw new Error('Wrong observation')
    expect(first.products).toHaveLength(6)
    expect(first.products[0].imageUrl).toBe('/images/cup.webp')
    first.products[0].stock = 999
    const next = await complete(buyer.observe({ view: 'product', productId: 'p1' }))
    expect(next.ok && next.view === 'product' && next.product.stock).toBe(8)
    expect(JSON.stringify(next)).not.toContain('costCents')
    expect(JSON.stringify(next)).not.toContain('base64')
  })

  it('updates balance, stock, orders and demonstration ranking together', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const receipt = await complete(buyer.execute(purchase()))
    expect(receipt.status).toBe('succeeded')
    const [products, ranking, me] = await snapshot()
    expect(products.ok && products.view === 'products' && products.products[0].stock).toBe(7)
    expect(ranking.ok && ranking.view === 'leaderboard' && ranking.leaderboard.find(m => m.id === 's1')?.revenueCents).toBe(137700)
    expect(me.ok && me.actor.balanceCents).toBe(41100)
    expect(me.ok && me.view === 'me' && me.orders).toHaveLength(1)
  })

  it.each([
    [0, 8900, 'p1', 'INVALID_QUANTITY'], [1.5, 8900, 'p1', 'INVALID_QUANTITY'],
    [9, 8900, 'p1', 'OUT_OF_STOCK'], [6, 8900, 'p1', 'INSUFFICIENT_BALANCE'],
    [1, 1, 'p1', 'PRICE_CHANGED'], [1, 8900, 'missing', 'PRODUCT_NOT_FOUND'],
  ])('rejects invalid purchase without any market change (%s, %s, %s)', async (quantity, price, productId, code) => {
    const before = await snapshot()
    const receipt = await complete(host.bindBuyer('buyer_001').execute({ id: 'invalid', type: 'purchase', payload: { quantity: quantity as number, expectedUnitPriceCents: price as number, productId: productId as string } }))
    expect(receipt.status === 'failed' && receipt.error.code).toBe(code)
    expect(await snapshot()).toEqual(before)
  })

  it('exposes pending and coalesces concurrent and completed semantic retries', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const first = buyer.execute(purchase())
    expect((await buyer.getReceipt('buy-1'))?.status).toBe('pending')
    const reordered = { payload: { quantity: 1, expectedUnitPriceCents: 8900, productId: 'p1' }, type: 'purchase', id: 'buy-1' } as Action
    const second = buyer.execute(reordered)
    const [a, b] = await complete(Promise.all([first, second]))
    expect(a.replayed).toBe(false)
    expect(b.replayed).toBe(true)
    expect((await buyer.execute(reordered)).replayed).toBe(true)
    const me = await complete(buyer.observe({ view: 'me' }))
    expect(me.ok && me.view === 'me' && me.orders).toHaveLength(1)
    expect(me.ok && me.actor.balanceCents).toBe(41100)
  })

  it('rejects reuse of an action ID with a different payload and preserves cached failures', async () => {
    const buyer = host.bindBuyer('buyer_001')
    await complete(buyer.execute(purchase()))
    const before = await snapshot()
    const conflict = await buyer.execute(purchase('buy-1', 2))
    expect(conflict.status === 'failed' && conflict.error.code).toBe('ACTION_ID_CONFLICT')
    expect(await snapshot()).toEqual(before)
    const bad = purchase('bad', 99)
    expect((await complete(buyer.execute(bad))).status).toBe('failed')
    expect((await buyer.execute(bad)).replayed).toBe(true)
  })

  it('serializes competing demo purchases and scopes action IDs to buyers', async () => {
    host.controls.updateProduct('p1', { stock: 1 })
    const one = host.bindBuyer('buyer_001')
    const two = host.bindBuyer('buyer_002')
    const results = await complete(Promise.all([one.execute(purchase()), two.execute(purchase())]))
    expect(results.map(r => r.status)).toEqual(['succeeded', 'failed'])
    expect(results[1].replayed).toBe(false)
    const second = await complete(two.observe({ view: 'me' }))
    expect(second.ok && second.actor.balanceCents).toBe(36000)
    expect(second.ok && second.view === 'me' && second.orders).toHaveLength(0)
  })

  it('separates send success from a later preset reply without duplicating either', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const action: Action = { id: 'message-1', type: 'send_public', payload: { merchantId: 's1', text: '杯盖能拆洗吗？' } }
    const receipt = await complete(buyer.execute(action))
    expect(receipt.status === 'succeeded' && receipt.result.type === 'message' && receipt.result.replyStatus).toBe('scheduled')
    const sent = await complete(buyer.observe({ view: 'public', merchantId: 's1' }))
    expect(sent.ok && sent.view === 'public' && sent.messages).toHaveLength(4)
    expect((await buyer.execute(action)).replayed).toBe(true)
    await vi.advanceTimersByTimeAsync(1000)
    const replied = await complete(buyer.observe({ view: 'public', merchantId: 's1' }))
    expect(replied.ok && replied.view === 'public' && replied.messages).toHaveLength(5)
    expect(replied.ok && replied.view === 'public' && replied.messages.at(-1)?.author.role).toBe('merchant')
  })

  it('keeps private observations and notifications within the bound buyer', async () => {
    const one = host.bindBuyer('buyer_001')
    const two = host.bindBuyer('buyer_002')
    const events: ChangeEvent[] = []
    two.subscribe(event => events.push(event))
    await complete(one.execute({ id: 'secret', type: 'send_private', payload: { merchantId: 's1', text: '仅本人可见 123' } }))
    await vi.advanceTimersByTimeAsync(1000)
    expect(events).toHaveLength(0)
    const mine = await complete(two.observe({ view: 'private', merchantId: 's1' }))
    expect(JSON.stringify(mine)).not.toContain('仅本人可见 123')
    expect(JSON.stringify(mine)).toContain('小禾，这是只属于你的私聊消息。')
  })

  it('rejects impersonation and unknown fields instead of widening visibility', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const query = { view: 'me', actorId: 'buyer_002' } as unknown as Query
    expect((await complete(buyer.observe(query))).ok).toBe(false)
    const input = { ...purchase(), actorId: 'buyer_002' } as unknown as Action
    expect((await buyer.execute(input)).status).toBe('failed')
    expect((await buyer.getReceipt('unknown'))).toBeNull()
    expect(await complete(buyer.observe({ view: 'private' } as Query))).toMatchObject({ ok: false })
  })

  it('does not emit or write messages when validation fails', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const listener = vi.fn()
    buyer.subscribe(listener)
    const before = await complete(buyer.observe({ view: 'public', merchantId: 's1' }))
    const bad: Action = { id: 'empty', type: 'send_public', payload: { merchantId: 's1', text: '  ' } }
    expect((await complete(buyer.execute(bad))).status).toBe('failed')
    await vi.advanceTimersByTimeAsync(2000)
    expect(await complete(buyer.observe({ view: 'public', merchantId: 's1' }))).toEqual(before)
    expect(listener).not.toHaveBeenCalled()
  })

  it('notifies external changes and supports unsubscribe', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const listener = vi.fn()
    const unsubscribe = buyer.subscribe(listener)
    host.controls.updateProduct('p1', { stock: 3 })
    host.controls.publishMessage('s1', '模拟外部公开发言')
    expect(listener).toHaveBeenCalledTimes(2)
    const product = await complete(buyer.observe({ view: 'product', productId: 'p1' }))
    expect(product.ok && product.view === 'product' && product.product.stock).toBe(3)
    unsubscribe()
    host.controls.updateProduct('p1', { stock: 4 })
    expect(listener).toHaveBeenCalledTimes(2)
  })

  it('supports deterministic loading/failure and same-ID retry before commit', async () => {
    const buyer = host.bindBuyer('buyer_001')
    const before = await snapshot()
    host.controls.failNext('execute')
    const rejected = expect(buyer.execute(purchase())).rejects.toMatchObject({ code: 'DEMO_TEMPORARY_FAILURE' })
    await vi.advanceTimersByTimeAsync(10)
    await rejected
    expect(await snapshot()).toEqual(before)
    expect(await buyer.getReceipt('buy-1')).toBeNull()
    expect((await complete(buyer.execute(purchase()))).status).toBe('succeeded')
    host.controls.failNext('observe')
    const readError = expect(buyer.observe({ view: 'me' })).rejects.toMatchObject({ code: 'DEMO_TEMPORARY_FAILURE' })
    await vi.advanceTimersByTimeAsync(10)
    await readError
    expect((await complete(buyer.observe({ view: 'me' }))).ok).toBe(true)
  })

  it('has a DOM-free Agent boundary without host controls and explicit network unavailability', async () => {
    const agent = createAgentBoundary(host.bindBuyer('buyer_001'))
    expect(Object.keys(agent).sort()).toEqual(['execute', 'getReceipt', 'observe'])
    expect((await complete(agent.observe({ view: 'product', productId: 'p1' })))).toMatchObject({ ok: true, view: 'product' })
    const real = createNotConnectedService()
    await expect(real.observe({ view: 'me' })).rejects.toMatchObject({ code: 'NOT_CONNECTED' })
    await expect(real.execute(purchase())).rejects.toMatchObject({ code: 'NOT_CONNECTED' })
  })
})
