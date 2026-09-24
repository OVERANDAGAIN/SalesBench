import type { BuyerService } from '../domain/types'

// Historical local-demo Agent facade only; real Agents must use sb-platform-v1.
// DOM-free, identity-bound JSON boundary. The host/test controller is not exposed.
export function createAgentBoundary(service: BuyerService) {
  return Object.freeze({
    observe: service.observe,
    execute: service.execute,
    getReceipt: service.getReceipt,
  })
}
