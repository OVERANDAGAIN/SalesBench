export interface Binding { session_id: string; actor_token: string }
export interface Identity { id: string; name: string }
export interface Listing { id: string; seller_id: string; product_id: string; unit_price_cents: number; description: string; active: boolean; offer_revision: number; content_revision: number }
export interface ListingView { listing: Listing; product: Identity; seller: Identity; available_quantity: number }
export interface MarketMessage { id: string; channel: 'public' | 'private'; author_id: string; seller_id: string; text: string; step: number; conversation_id: string | null }
export interface MarketOrder { id: string; buyer_id: string; seller_id: string; listing_id: string; product_id: string; quantity: number; unit_price_cents: number; total_cents: number; step: number; offer_revision: number }
export interface Offer { id: string; supplier_id: string; product_id: string; unit_cost_cents: number; available_quantity: number; active: boolean }
export interface OwnObservation {
  actor: Identity; account: { actor_id: string; balance_cents: number }; products: Identity[];
  inventory: { seller_id: string; product_id: string; quantity: number }[]; listings: ListingView[];
  offers: Offer[]; orders: MarketOrder[]; messages: MarketMessage[];
  conversations: { id: string; buyer_id: string; seller_id: string }[];
}
export interface AuthorizedState {
  public: { version: number; time: { step: number }; sellers: Identity[]; listings: ListingView[]; messages: MarketMessage[] };
  own: OwnObservation; inbox: OwnObservation;
}
export interface Context { round: number; tick: number; wave: string }
export interface Wave { name: string; role: 'seller' | 'buyer'; allowed_actions: string[]; max_actions: number; max_messages: number; max_purchases: number }
export interface Opportunity { opportunity_id: string; context: Context; wave: Wave; state: AuthorizedState; procurement: OwnObservation | null }
export interface Runtime { status: string; runner_phase: string; published_version: number; engine_step: number; next_boundary: { context: Context; wave: Wave | null } | null }
export interface MarketObservation { schema_version: 'sb-platform-v1'; session_id: string; actor_id: string; published_version: number; state: AuthorizedState; opportunity: Opportunity | null; runtime: Runtime }
export type MarketAction =
  | { type: 'procure'; offer_id: string; quantity: number; expected_unit_cost_cents: number }
  | { type: 'create_listing'; listing_id: string; product_id: string; unit_price_cents: number; description: string }
  | { type: 'update_listing'; listing_id: string; unit_price_cents?: number; description?: string; active?: boolean }
  | { type: 'send_public'; seller_id: string; text: string }
  | { type: 'send_private'; recipient_id: string; text: string }
  | { type: 'purchase'; listing_id: string; quantity: number; expected_unit_price_cents: number; expected_offer_revision: number }
  | { type: 'wait' }
export interface BatchRequest { request_id: string; observation_version: number; opportunity_id: string; actions: MarketAction[] }
export interface Outcome { action_id: string; status: string; reason?: string | null; result?: { ok: boolean; code: string; entity_id: string | null; step: number } | null }
export interface BatchReceipt { session_id: string; actor_id: string; request_id: string; opportunity_id: string; status: 'pending' | 'rejected' | 'succeeded' | 'failed' | 'aborted'; code: string | null; submitted_version: number; published_version: number; outcomes: Outcome[]; replayed?: boolean }
