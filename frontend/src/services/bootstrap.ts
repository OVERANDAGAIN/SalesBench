import { createDemoHost } from '../demo/service'
import type { BuyerService } from '../domain/types'

// Legacy regression only. The participant entry is NetworkApp / MarketClient.
if (!import.meta.env.DEV || import.meta.env.VITE_BUYER_SERVICE !== 'demo') throw new Error('Local demo requires explicit development mode')
const host = createDemoHost()
export const buyerService: BuyerService = host.bindBuyer('buyer_001')
if (import.meta.hot) import.meta.hot.dispose(() => host.dispose())
