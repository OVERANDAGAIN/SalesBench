import { createDemoHost } from '../demo/service'
import { createNotConnectedService } from './notConnected'
import type { BuyerService } from '../domain/types'

const mode = import.meta.env.VITE_BUYER_SERVICE ?? 'demo'
export const demoMode = mode === 'demo'
const host = demoMode ? createDemoHost() : null
export const buyerService: BuyerService = host ? host.bindBuyer('buyer_001') : createNotConnectedService()
if (import.meta.hot) import.meta.hot.dispose(() => host?.dispose())
