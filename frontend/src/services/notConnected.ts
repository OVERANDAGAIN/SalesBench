import type { BuyerService } from '../domain/types'
import { ServiceUnavailable } from './errors'

// Intentional seam for a future authenticated FastAPI business adapter.
// There are no business endpoints yet; never fabricate a successful response.
export function createNotConnectedService(): BuyerService {
  const unavailable = async (): Promise<never> => {
    throw new ServiceUnavailable('NOT_CONNECTED', '真实业务接口尚未接入，未切换为演示数据。')
  }
  return { observe: unavailable, execute: unavailable, getReceipt: unavailable, subscribe: () => () => {} }
}
