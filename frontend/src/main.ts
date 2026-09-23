import { createApp } from 'vue'
import App from './App.vue'
import { buyerService, demoMode } from './services/bootstrap'
import { createAgentBoundary } from './services/agent'
import './styles/prototype.css'
import './styles/app.css'

// Optional browser convenience only. The same Agent module runs without a DOM.
Object.defineProperty(window, 'salesbench', { value: createAgentBoundary(buyerService), configurable: true })

createApp(App, { service: buyerService, demoMode }).mount('#app')
