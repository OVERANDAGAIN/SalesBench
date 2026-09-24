export const SCHEMA_VERSION = '0.1-draft' as const
export type Page = 'leaderboard' | 'products' | 'public' | 'private' | 'me'
export type Channel = 'public' | 'private'
export interface Actor { id: string; name: string; balanceCents: number }
export interface Merchant {
  id: string; name: string; initial: string; color: string; tag: string
  description: string; pitch: string; featuredProductId: string
}
export interface LeaderboardRow extends Merchant { rank: number | null; revenueCents: number | null; sold: number | null }
export interface Product {
  id: string; merchantId: string; name: string; variant: string; category: string
  priceCents: number; stock: number; imageUrl: string; specs: string[]; description: string
  offerRevision?: number; contentRevision?: number
}
export interface Message {
  id: string; merchantId: string; channel: Channel
  author: { id: string; name: string; role: 'buyer' | 'merchant' }
  text: string; createdAt: string; isPreset: boolean
}
export interface Order {
  id: string; productId: string; productName: string; variant: string
  merchantId: string; merchantName: string; unitPriceCents: number
  quantity: number; totalCents: number; createdAt: string; status: 'simulated_completed' | 'completed'
}
export interface Account { initialBalanceCents: number | null; spentCents: number }
export interface Conversation { merchantId: string; lastMessage: Message }
export type Query =
  | { view: 'leaderboard' | 'me' }
  | { view: 'products'; merchantId?: string }
  | { view: 'product'; productId: string }
  | { view: 'public' | 'private'; merchantId: string }
interface ObservationBase {
  ok: true; schemaVersion: typeof SCHEMA_VERSION | 'sb-platform-v1'; mode: 'local-demo' | 'network'
  sessionId: string; revision: number; actor: Actor; merchants: Merchant[]
}
export type Observation = ObservationBase & (
  | { view: 'leaderboard'; leaderboard: LeaderboardRow[] }
  | { view: 'products'; products: Product[] }
  | { view: 'product'; product: Product }
  | { view: 'public'; merchantId: string; products: Product[]; messages: Message[] }
  | { view: 'private'; merchantId: string; products: Product[]; messages: Message[]; conversations: Conversation[] }
  | { view: 'me'; account: Account; orders: Order[] }
)
export interface ServiceIssue { code: string; message: string; retryable: boolean }
export type ObservationResult = Observation | { ok: false; error: ServiceIssue }
export type Action =
  | { id: string; type: 'purchase'; payload: { productId: string; quantity: number; expectedUnitPriceCents: number; expectedOfferRevision?: number } }
  | { id: string; type: 'send_public' | 'send_private'; payload: { merchantId: string; text: string } }
export type ActionResult =
  | { type: 'purchase'; order: Order; balanceCents: number; remainingStock: number }
  | { type: 'message'; messageId: string; merchantId: string; channel: Channel; replyStatus: 'scheduled' }
interface ReceiptBase {
  schemaVersion: typeof SCHEMA_VERSION; actionId: string | null; actorId: string
  sessionId: string; revision: number; replayed: boolean
}
export type Receipt = ReceiptBase & (
  | { ok: false; status: 'pending' }
  | { ok: true; status: 'succeeded'; result: ActionResult }
  | { ok: false; status: 'failed'; error: ServiceIssue }
)
export type Topic = 'products' | 'leaderboard' | 'account' | 'orders' | 'messages'
export interface ChangeEvent {
  sessionId: string; revision: number; topics: Topic[]; merchantId?: string; channel?: Channel
}
export interface BuyerService {
  observe(query: Query): Promise<ObservationResult>
  execute(action: Action): Promise<Receipt>
  getReceipt(actionId: string): Promise<Receipt | null>
  subscribe(listener: (event: ChangeEvent) => void): () => void
}
