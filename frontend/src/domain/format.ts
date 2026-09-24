export const amount = (cents: number) => (cents / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const price = (cents: number) => (cents / 100).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
export const time = (iso: string) => iso.startsWith('step:') ? `Step ${iso.slice(5)}` : new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
