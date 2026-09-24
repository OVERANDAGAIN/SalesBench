import { createApp } from 'vue'
import App from './App.vue'
import NetworkApp from './NetworkApp.vue'
import './styles/prototype.css'
import './styles/app.css'

// Legacy demonstration is explicit and development-only, never a network fallback.
if (import.meta.env.DEV && import.meta.env.VITE_BUYER_SERVICE === 'demo') {
  const { buyerService } = await import('./services/bootstrap')
  const { createAgentBoundary } = await import('./services/agent')
  Object.defineProperty(window, 'salesbench', { value: createAgentBoundary(buyerService), configurable: true })
  createApp(App, { service: buyerService, demoMode: true }).mount('#app')
} else createApp(NetworkApp).mount('#app')
