import type { BuyerService } from '../domain/types'
import { ServiceUnavailable } from './errors'

// Historical SB-002B test fixture for the old single-action BuyerService contract.
// Current participants use platform/MarketClient; this is never its fallback.
export function createNotConnectedService(): BuyerService {
  const unavailable = async (): Promise<never> => {
    throw new ServiceUnavailable('NOT_CONNECTED', '真实业务接口尚未接入，未切换为演示数据。')
  }
  return { observe: unavailable, execute: unavailable, getReceipt: unavailable, subscribe: () => () => {} }
}
