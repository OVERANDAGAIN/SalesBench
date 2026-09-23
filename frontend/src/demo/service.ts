import {
  SCHEMA_VERSION, type Action, type ActionResult, type BuyerService, type ChangeEvent,
  type Channel, type Message, type ObservationResult, type Order, type Query,
  type Receipt, type ServiceIssue, type Topic,
} from '../domain/types'
import { ServiceUnavailable } from '../services/errors'
import { merchantSeeds, productSeeds, publicMessageSeeds } from './seed'

interface BuyerState {
  id: string; name: string; balanceCents: number; initialBalanceCents: number
  orders: Order[]; revision: number; privateMessages: Record<string, Message[]>
}
interface Entry { fingerprint: string; receipt: Receipt; promise: Promise<Receipt> }
interface DemoOptions { latencyMs?: number; replyDelayMs?: number; clock?: () => string }
const copy = <T>(value: T): T => structuredClone(value)
const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value) &&
  (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null)
const only = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).every(key => keys.includes(key))
const issue = (code: string, message: string): ServiceIssue => ({ code, message, retryable: false })
function canonical(value: unknown): string {
  if (record(value)) return JSON.stringify(Object.keys(value).sort().map(key => [key, canonical(value[key])]))
  return JSON.stringify(value)
}

/** In-memory demo host, not a Python experiment kernel or a production authorization layer. */
export function createDemoHost(options: DemoOptions = {}) {
  const latency = options.latencyMs ?? 140
  const replyDelay = options.replyDelayMs ?? 950
  const clock = options.clock ?? (() => new Date().toISOString())
  const sessionId = 'demo-session-01'
  const merchants = copy(merchantSeeds)
  const products = copy(productSeeds)
  const publicMessages: Record<string, Message[]> = {}
  for (const merchant of merchants) {
    const seeds = publicMessageSeeds[merchant.id as keyof typeof publicMessageSeeds]
    publicMessages[merchant.id] = seeds.map(seed => ({
      id: seed.id, merchantId: merchant.id, channel: 'public',
      author: { id: seed.role === 'merchant' ? merchant.id : `seed-${seed.authorName}`, name: seed.authorName, role: seed.role as 'merchant' | 'buyer' },
      text: seed.text, createdAt: new Date(`2026-09-23T${seed.time}:00+08:00`).toISOString(), isPreset: true,
    }))
  }
  const buyers: Record<string, BuyerState> = {}
  for (const [id, name, balance] of [['buyer_001', '体验买家', 50000], ['buyer_002', '小禾', 36000]] as const) {
    buyers[id] = {
      id, name, balanceCents: balance, initialBalanceCents: balance, orders: [], revision: 0,
      privateMessages: Object.fromEntries(merchants.map(m => [m.id, [{
        id: `welcome-${id}-${m.id}`, merchantId: m.id, channel: 'private',
        author: { id: m.id, name: m.name, role: 'merchant' },
        text: id === 'buyer_002' ? '小禾，这是只属于你的私聊消息。' : `你好，这里是${m.name}。可以告诉我你想了解的商品；也可以先去浏览，不必急着决定。`,
        createdAt: '2026-09-23T02:20:00.000Z', isPreset: true,
      }]])),
    }
  }
  let sequence = 10
  let disposed = false
  const entries = new Map<string, Entry>()
  const subscriptions = new Set<{ buyerId: string; callback: (event: ChangeEvent) => void }>()
  const waits = new Map<ReturnType<typeof setTimeout>, (reason: Error) => void>()
  const replies = new Set<ReturnType<typeof setTimeout>>()
  const failures = { observe: 0, execute: 0 }

  function pause() {
    if (disposed) return Promise.reject(new ServiceUnavailable('DISPOSED', '演示会话已结束。'))
    return new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => { waits.delete(timer); resolve() }, latency)
      waits.set(timer, reject)
    })
  }
  function maybeFail(operation: keyof typeof failures) {
    if (failures[operation] > 0) {
      failures[operation]--
      throw new ServiceUnavailable('DEMO_TEMPORARY_FAILURE', '模拟服务暂时不可用，请重试；本次请求尚未提交。')
    }
  }
  function notify(topics: Topic[], options: { owner?: string; privateFor?: string; merchantId?: string; channel?: Channel } = {}) {
    for (const buyer of Object.values(buyers)) {
      if (options.privateFor && buyer.id !== options.privateFor) continue
      const visibleTopics = topics.filter(topic => !['account', 'orders'].includes(topic) || buyer.id === options.owner)
      if (!visibleTopics.length) continue
      buyer.revision++
      const event: ChangeEvent = { sessionId, revision: buyer.revision, topics: visibleTopics }
      if (options.merchantId) event.merchantId = options.merchantId
      if (options.channel) event.channel = options.channel
      for (const subscription of subscriptions) {
        if (subscription.buyerId !== buyer.id) continue
        try { subscription.callback(copy(event)) } catch { /* Observer failure cannot undo a completed demo action. */ }
      }
    }
  }
  function merchantViews() {
    return merchants.map(({ revenueCents: _revenue, sold: _sold, ...merchant }) => copy(merchant))
  }
  function replyText(merchantId: string, text: string) {
    if (/便宜|折扣|优惠|降价/.test(text)) return '本场演示按商品标价成交，暂不提供议价或优惠。你可以比较其他商品，也可以选择暂不购买。'
    if (/贵|价格|多少钱/.test(text)) return '价格以商品卡片为准，确认购买前会再展示总价和剩余余额。你可以先比较，再决定是否购买。'
    return ({
      s1: '这款杯子是陶瓷内胆，杯盖可拆洗，建议手洗。它不是保温杯，也不建议倒置携带。380mL 和 500mL 可以按你的习惯选择。',
      s2: '基础款续航约 20 小时，长续航款约 40 小时。两款均支持蓝牙连接、折叠收纳，不含主动降噪。可以先看详情再决定。',
      s3: '标准款可放 13 英寸电脑，加大款可放 15 英寸电脑；都是开放式袋口，没有拉链。商品卡片中可以查看尺寸和价格。',
    } as Record<string, string>)[merchantId]
  }
  function scheduleReply(buyer: BuyerState, merchantId: string, channel: Channel, text: string) {
    const timer = setTimeout(() => {
      replies.delete(timer)
      if (disposed) return
      const merchant = merchants.find(m => m.id === merchantId)!
      const list = channel === 'public' ? publicMessages[merchantId] : buyer.privateMessages[merchantId]
      list.push({ id: `msg-${++sequence}`, merchantId, channel, author: { id: merchant.id, name: merchant.name, role: 'merchant' }, text: replyText(merchantId, text), createdAt: clock(), isPreset: true })
      notify(['messages'], { merchantId, channel, privateFor: channel === 'private' ? buyer.id : undefined })
    }, replyDelay)
    replies.add(timer)
  }

  function bindBuyer(buyerId: string): BuyerService {
    if (!Object.hasOwn(buyers, buyerId)) throw new Error('Unknown local demo buyer')
    const buyer = buyers[buyerId]
    const receiptBase = (id: string | null) => ({ schemaVersion: SCHEMA_VERSION, actionId: id, actorId: buyer.id, sessionId, revision: buyer.revision, replayed: false })
    const failed = (id: string | null, error: ServiceIssue): Receipt => ({ ...receiptBase(id), ok: false, status: 'failed', error })
    function read(query: unknown): ObservationResult {
      const invalid = (message = '观察参数不支持切换身份或读取内部状态。'): ObservationResult => ({ ok: false, error: issue('INVALID_QUERY', message) })
      if (!record(query) || !only(query, ['view', 'merchantId', 'productId'])) return invalid()
      if (!['leaderboard', 'products', 'product', 'public', 'private', 'me'].includes(String(query.view))) return invalid('未知观察页面。')
      const allowed = query.view === 'product' ? ['view', 'productId'] : ['products', 'public', 'private'].includes(String(query.view)) ? ['view', 'merchantId'] : ['view']
      if (!only(query, allowed)) return invalid()
      if (query.merchantId !== undefined && (typeof query.merchantId !== 'string' || !merchants.some(m => m.id === query.merchantId))) return { ok: false, error: issue('MERCHANT_NOT_FOUND', '商家不存在。') }
      const base = { ok: true as const, schemaVersion: SCHEMA_VERSION, mode: 'local-demo' as const, sessionId, revision: buyer.revision, actor: { id: buyer.id, name: buyer.name, balanceCents: buyer.balanceCents }, merchants: merchantViews() }
      switch (query.view) {
        case 'leaderboard': return { ...base, view: 'leaderboard', leaderboard: copy([...merchants].sort((a, b) => b.revenueCents - a.revenueCents || a.id.localeCompare(b.id)).map((m, i) => ({ ...m, rank: i + 1 }))) }
        case 'products': return { ...base, view: 'products', products: copy(products.filter(p => !query.merchantId || p.merchantId === query.merchantId)) }
        case 'product': {
          const product = products.find(p => p.id === query.productId)
          return product ? { ...base, view: 'product', product: copy(product) } : { ok: false, error: issue('PRODUCT_NOT_FOUND', '商品不存在。') }
        }
        case 'public': case 'private': {
          if (typeof query.merchantId !== 'string') return invalid('请选择商家。')
          const merchantId = query.merchantId
          const common = { ...base, merchantId, products: copy(products.filter(p => p.merchantId === merchantId)) }
          if (query.view === 'public') return { ...common, view: 'public', messages: copy(publicMessages[merchantId]) }
          return { ...common, view: 'private', messages: copy(buyer.privateMessages[merchantId]), conversations: merchants.map(m => ({ merchantId: m.id, lastMessage: copy(buyer.privateMessages[m.id].at(-1)!) })) }
        }
        case 'me': return { ...base, view: 'me', account: { initialBalanceCents: buyer.initialBalanceCents, spentCents: buyer.initialBalanceCents - buyer.balanceCents }, orders: copy(buyer.orders) }
        default: return invalid()
      }
    }
    function commit(action: Action): Receipt {
      const fail = (code: string, message: string) => failed(action.id, issue(code, message))
      let result: ActionResult
      if (action.type === 'purchase') {
        const { productId, quantity, expectedUnitPriceCents } = action.payload
        const product = products.find(p => p.id === productId)
        if (!product) return fail('PRODUCT_NOT_FOUND', '商品不存在。')
        if (!Number.isInteger(quantity) || quantity < 1 || quantity > 99) return fail('INVALID_QUANTITY', '数量必须是 1–99 的整数。')
        if (expectedUnitPriceCents !== product.priceCents) return fail('PRICE_CHANGED', '价格已变化，请返回详情重新确认。')
        if (quantity > product.stock) return fail('OUT_OF_STOCK', '剩余库存不足，请调整数量。')
        const totalCents = product.priceCents * quantity
        if (totalCents > buyer.balanceCents) return fail('INSUFFICIENT_BALANCE', '模拟余额不足，可以继续浏览其他商品。')
        const merchant = merchants.find(m => m.id === product.merchantId)!
        const order: Order = { id: `SB-${String(++sequence).padStart(5, '0')}`, productId: product.id, productName: product.name, variant: product.variant, merchantId: merchant.id, merchantName: merchant.name, unitPriceCents: product.priceCents, quantity, totalCents, createdAt: clock(), status: 'simulated_completed' }
        // No await between validation and all in-memory mutations. Not a database transaction.
        buyer.balanceCents -= totalCents
        product.stock -= quantity
        merchant.revenueCents += totalCents
        merchant.sold += quantity
        buyer.orders.unshift(order)
        notify(['products', 'leaderboard', 'account', 'orders'], { owner: buyer.id })
        result = { type: 'purchase', order: copy(order), balanceCents: buyer.balanceCents, remainingStock: product.stock }
      } else {
        const { merchantId, text } = action.payload
        if (!merchants.some(m => m.id === merchantId)) return fail('MERCHANT_NOT_FOUND', '商家不存在。')
        if (typeof text !== 'string' || !text.trim() || text.trim().length > 500) return fail('INVALID_MESSAGE', '请输入 1–500 字的消息。')
        const channel: Channel = action.type === 'send_public' ? 'public' : 'private'
        const message: Message = { id: `msg-${++sequence}`, merchantId, channel, author: { id: buyer.id, name: buyer.name, role: 'buyer' }, text: text.trim(), createdAt: clock(), isPreset: false }
        const list = channel === 'public' ? publicMessages[merchantId] : buyer.privateMessages[merchantId]
        list.push(message)
        notify(['messages'], { merchantId, channel, privateFor: channel === 'private' ? buyer.id : undefined })
        scheduleReply(buyer, merchantId, channel, text)
        result = { type: 'message', messageId: message.id, merchantId, channel, replyStatus: 'scheduled' }
      }
      return { ...receiptBase(action.id), ok: true, status: 'succeeded', result }
    }
    async function execute(input: unknown): Promise<Receipt> {
      const id = record(input) && typeof input.id === 'string' ? input.id : null
      if (!record(input) || !only(input, ['id', 'type', 'payload']) || !id?.trim() || id.length > 100 || !record(input.payload)) return failed(id, issue('INVALID_ACTION', '动作必须包含 id、type 和 payload，不能指定其他身份。'))
      const keys = input.type === 'purchase' ? ['productId', 'quantity', 'expectedUnitPriceCents'] : ['send_public', 'send_private'].includes(String(input.type)) ? ['merchantId', 'text'] : null
      if (!keys) return failed(id, issue('INVALID_ACTION', '不支持的动作类型。'))
      if (!only(input.payload, keys) || keys.some(key => !Object.hasOwn(input.payload as object, key))) return failed(id, issue('INVALID_PAYLOAD', '动作字段不完整或包含不支持的字段。'))
      const action = copy(input) as unknown as Action
      const key = `${sessionId}:${buyerId}:${id}`
      const fingerprint = canonical(action)
      const existing = entries.get(key)
      if (existing) {
        if (existing.fingerprint !== fingerprint) return failed(id, issue('ACTION_ID_CONFLICT', '同一动作编号不能用于不同操作。'))
        return { ...copy(await existing.promise), replayed: true }
      }
      const receipt: Receipt = { ...receiptBase(id), ok: false, status: 'pending' }
      const promise = (async () => {
        await pause()
        maybeFail('execute')
        const final = commit(action)
        const entry = entries.get(key)
        if (entry) entry.receipt = copy(final)
        return final
      })()
      entries.set(key, { fingerprint, receipt, promise })
      try { return copy(await promise) } catch (error) { entries.delete(key); throw error }
    }
    return Object.freeze({
      async observe(query: Query) { await pause(); maybeFail('observe'); return read(query) },
      execute,
      async getReceipt(actionId: string) { return copy(entries.get(`${sessionId}:${buyerId}:${actionId}`)?.receipt ?? null) },
      subscribe(callback: (event: ChangeEvent) => void) {
        const subscription = { buyerId, callback }
        subscriptions.add(subscription)
        return () => { subscriptions.delete(subscription) }
      },
    })
  }
  return {
    bindBuyer,
    // Only the demo/test host receives these controls. Not exported to window or Agent.
    controls: {
      failNext(operation: keyof typeof failures) { failures[operation]++ },
      updateProduct(productId: string, patch: { stock?: number; priceCents?: number }) {
        const product = products.find(p => p.id === productId)
        if (!product || Object.entries(patch).some(([key, value]) => !['stock', 'priceCents'].includes(key) || !Number.isSafeInteger(value) || value < (key === 'stock' ? 0 : 1))) throw new Error('Invalid demo product patch')
        Object.assign(product, patch)
        notify(['products'])
      },
      publishMessage(merchantId: string, text: string, privateFor?: string) {
        if (!merchants.some(m => m.id === merchantId) || (privateFor && !Object.hasOwn(buyers, privateFor))) throw new Error('Invalid demo message target')
        const channel: Channel = privateFor ? 'private' : 'public'
        const list = privateFor ? buyers[privateFor].privateMessages[merchantId] : publicMessages[merchantId]
        list.push({ id: `external-${++sequence}`, merchantId, channel, author: { id: 'demo-external', name: '阿远', role: 'buyer' }, text, createdAt: clock(), isPreset: true })
        notify(['messages'], { merchantId, channel, privateFor })
      },
    },
    dispose() {
      disposed = true
      for (const [timer, reject] of waits) { clearTimeout(timer); reject(new ServiceUnavailable('DISPOSED', '演示会话已结束。')) }
      waits.clear()
      for (const timer of replies) clearTimeout(timer)
      replies.clear()
      subscriptions.clear()
    },
  }
}
