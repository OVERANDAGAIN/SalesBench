import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import net from 'node:net'
import { chromium } from 'playwright-core'

const frontend = fileURLToPath(new URL('../..', import.meta.url))
const root = path.dirname(frontend)
const config = JSON.parse(await readFile(path.join(root, '.local/runtime.json'), 'utf8'))
const evidence = path.join(root, '.local/SB-002B-regression')
await mkdir(evidence, { recursive: true })
const temp = path.join(config.cache, 'browser-temp')
await mkdir(temp, { recursive: true })
process.env.TEMP = temp
process.env.TMP = temp
const steps = []
const errors = []
let browser
let server
let log = ''
const port = 5173
await new Promise((resolve, reject) => {
  const probe = net.createServer()
  probe.once('error', () => reject(new Error('5173 is occupied; no existing service will be stopped')))
  probe.listen(port, '127.0.0.1', () => probe.close(resolve))
})
async function check(name, work) { await work(); steps.push(name); console.log('PASS ' + name) }
async function stopOwnedServer() {
  if (!server || server.exitCode !== null) return
  if (process.platform === 'win32') {
    await new Promise(resolve => { const stop = spawn('taskkill.exe', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }); stop.on('exit', resolve) })
  } else server.kill('SIGTERM')
}
try {
  server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: frontend, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, VITE_BUYER_SERVICE: 'demo' } })
  server.stdout.on('data', data => { log += data })
  server.stderr.on('data', data => { log += data })
  let ready = false
  for (let attempt = 0; attempt < 50; attempt++) {
    try { if ((await fetch('http://127.0.0.1:5173')).ok) { ready = true; break } } catch {}
    await new Promise(resolve => setTimeout(resolve, 200))
  }
  assert(ready, 'Vite did not start')
  browser = await chromium.launch({ executablePath: config.browser, headless: true, chromiumSandbox: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, locale: 'zh-CN' })
  page.setDefaultTimeout(10000)
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()) })
  const readyPage = async () => { await page.locator('main[aria-busy="false"]').waitFor(); await page.locator('.loading-status').waitFor({ state: 'detached' }) }
  const nav = async (label, heading) => {
    await page.getByRole('navigation', { name: '主导航' }).getByRole('button', { name: label, exact: true }).click()
    await page.getByRole('heading', { name: heading, exact: true }).waitFor()
    await readyPage()
  }
  const screenshot = async name => { await page.screenshot({ path: path.join(evidence, name + '.png'), fullPage: !/detail|checkout|purchase-result|price-change/.test(name) }) }
  const observe = async query => page.evaluate(query => window.salesbench.observe(query), query)
  const noOverflow = async () => { assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Horizontal document overflow') }
  const headings = [
    ['排行榜', '看看商家们的表现', 'ranking'], ['商品推荐', '发现适合你的好物', 'products'],
    ['公共交流', '一起聊聊，了解更多', 'public'], ['私聊', '和商家单独聊聊', 'private'], ['我的', '我的购买与余额', 'account'],
  ]
  await page.goto('http://127.0.0.1:5173')
  await readyPage()
  await check('desktop five-page navigation and layout', async () => {
    assert.deepEqual(await page.getByRole('navigation').getByRole('button').allTextContents(), headings.map(row => row[0]))
    for (const [label, heading, file] of headings) { await nav(label, heading); await noOverflow(); await screenshot('desktop-' + file) }
    assert.deepEqual(await page.evaluate(() => Object.keys(window.salesbench).sort()), ['execute', 'getReceipt', 'observe'])
  })
  await check('product filtering, detail and explicit non-purchase', async () => {
    await nav('商品推荐', '发现适合你的好物')
    assert.equal(await page.locator('.product-card').count(), 6)
    await page.locator('.filters').getByRole('button', { name: '松间生活', exact: true }).click()
    await readyPage(); assert.equal(await page.locator('.product-card').count(), 2)
    await page.locator('.filters').getByRole('button', { name: '全部商家', exact: true }).click(); await readyPage()
    await page.getByRole('button', { name: '查看陶瓷随行杯详情', exact: true }).click()
    await page.getByRole('dialog', { name: '商品详情' }).waitFor()
    await screenshot('desktop-detail')
    await page.getByRole('button', { name: '暂不购买', exact: true }).click()
    await page.getByText('已选择暂不购买，余额不变。', { exact: true }).waitFor()
    const me = await observe({ view: 'me' }); assert.equal(me.actor.balanceCents, 50000); assert.equal(me.orders.length, 0)
  })
  await check('public message and delayed preset reply; draft isolation', async () => {
    await page.getByRole('button', { name: '查看陶瓷随行杯详情', exact: true }).click()
    await page.getByRole('dialog', { name: '商品详情' }).getByRole('button', { name: '公开交流', exact: true }).click(); await readyPage()
    await page.getByRole('textbox', { name: '公开消息内容' }).fill('杯盖可以拆下来清洗吗？本轮浏览器验证。')
    await page.getByRole('button', { name: '发送', exact: true }).click()
    await page.getByRole('log').getByText('杯盖可以拆下来清洗吗？本轮浏览器验证。', { exact: true }).waitFor()
    await page.getByRole('log').getByText('这款杯子是陶瓷内胆', { exact: false }).waitFor()
    await readyPage(); await screenshot('desktop-public-sent')
    await page.getByRole('textbox', { name: '公开消息内容' }).fill('保留公开草稿')
    await page.getByRole('button', { name: '私聊商家', exact: true }).click(); await readyPage()
    assert.equal(await page.getByRole('textbox', { name: '私聊消息内容' }).inputValue(), '')
  })
  await check('private send, public/private separation and product link', async () => {
    await page.getByRole('textbox', { name: '私聊消息内容' }).fill('有优惠吗？这条是私聊验证。')
    await page.getByRole('button', { name: '发送', exact: true }).click()
    await page.getByRole('log').getByText('本场演示按商品标价成交', { exact: false }).waitFor()
    await readyPage(); await screenshot('desktop-private-sent')
    await page.getByRole('button', { name: '去公开交流', exact: true }).click(); await readyPage()
    assert.equal(await page.getByRole('textbox', { name: '公开消息内容' }).inputValue(), '保留公开草稿')
    assert.equal(await page.getByRole('log').getByText('有优惠吗？这条是私聊验证。', { exact: true }).count(), 0)
    await page.getByRole('button', { name: '查看商品 →', exact: true }).click()
    await page.getByRole('dialog', { name: '商品详情' }).waitFor()
  })
  await check('quantity validation, purchase result, account and ranking consistency', async () => {
    await page.getByRole('button', { name: '购买此商品', exact: true }).click()
    await page.getByRole('dialog', { name: '确认模拟购买' }).waitFor()
    await page.getByLabel('购买数量', { exact: false }).fill('0')
    assert(await page.getByRole('button', { name: '确认购买', exact: true }).isDisabled())
    await page.getByLabel('购买数量', { exact: false }).fill('1')
    await screenshot('desktop-checkout')
    await page.getByRole('button', { name: '确认购买', exact: true }).click()
    await page.getByRole('heading', { name: '已完成模拟购买', exact: true }).waitFor()
    await screenshot('desktop-purchase-result')
    await page.getByRole('button', { name: '查看购买历史', exact: true }).click(); await readyPage()
    await screenshot('desktop-account-purchased')
    const me = await observe({ view: 'me' }); assert.equal(me.actor.balanceCents, 41100); assert.equal(me.orders.length, 1)
    const item = await observe({ view: 'product', productId: 'p1' }); assert.equal(item.product.stock, 7)
    const rank = await observe({ view: 'leaderboard' }); assert.equal(rank.leaderboard.find(m => m.id === 's1').revenueCents, 137700)
  })
  await check('direct purchase, continue browsing and browser Agent replay', async () => {
    await page.getByRole('button', { name: '继续浏览', exact: true }).click(); await readyPage()
    const card = page.locator('.product-card').filter({ has: page.getByRole('heading', { name: '日常帆布托特包', exact: true }) })
    await card.getByRole('button', { name: '直接购买', exact: true }).click()
    await page.getByRole('button', { name: '确认购买', exact: true }).click()
    await page.getByRole('heading', { name: '已完成模拟购买', exact: true }).waitFor()
    await page.getByRole('button', { name: '继续浏览', exact: true }).click(); await readyPage()
    const action = { id: 'browser-agent-replay', type: 'purchase', payload: { productId: 'p2', quantity: 1, expectedUnitPriceCents: 10900 } }
    const first = await page.evaluate(action => window.salesbench.execute(action), action)
    const repeat = await page.evaluate(action => window.salesbench.execute(action), action)
    assert.equal(first.status, 'succeeded'); assert.equal(repeat.replayed, true)
    await nav('我的', '我的购买与余额')
    const me = await observe({ view: 'me' }); assert.equal(me.actor.balanceCents, 25300); assert.equal(me.orders.length, 3)
    assert.equal(await page.locator('.history tbody tr').count(), 3)
  })
  await check('refresh resets demo; narrow-screen five pages and modal', async () => {
    await page.setViewportSize({ width: 390, height: 844 }); await page.reload(); await readyPage()
    assert.equal((await observe({ view: 'me' })).actor.balanceCents, 50000)
    for (const [label, heading, file] of headings) { await nav(label, heading); await noOverflow(); await screenshot('mobile-' + file) }
    await nav('商品推荐', '发现适合你的好物')
    await page.getByRole('button', { name: '查看陶瓷随行杯详情', exact: true }).click()
    await page.getByRole('dialog', { name: '商品详情' }).waitFor(); await screenshot('mobile-detail')
    await page.getByRole('button', { name: '购买此商品', exact: true }).click()
    await page.getByRole('dialog', { name: '确认模拟购买' }).waitFor(); await screenshot('mobile-checkout')
    await page.getByRole('button', { name: '暂不购买', exact: true }).click()
    assert.equal((await observe({ view: 'me' })).orders.length, 0)
    await nav('私聊', '和商家单独聊聊')
    await page.getByRole('textbox', { name: '私聊消息内容' }).fill('窄屏发送与滚动验证')
    await page.getByRole('button', { name: '发送', exact: true }).click()
    await page.getByRole('log').getByText('窄屏发送与滚动验证', { exact: true }).waitFor()
    await page.getByRole('log').getByText('这款杯子是陶瓷内胆', { exact: false }).waitFor()
    await readyPage()
    await page.getByRole('button', { name: '查看商品', exact: true }).click()
    await page.getByRole('button', { name: '购买此商品', exact: true }).click()
    await page.getByRole('button', { name: '确认购买', exact: true }).click()
    await page.getByRole('heading', { name: '已完成模拟购买', exact: true }).waitFor()
    await page.getByRole('button', { name: '查看购买历史', exact: true }).click(); await readyPage()
    assert.equal((await observe({ view: 'me' })).orders.length, 1)
    await screenshot('mobile-account-purchased')
    await page.setViewportSize({ width: 320, height: 740 })
    for (const [label, heading] of headings) { await nav(label, heading); await noOverflow() }
  })
  await check('UI loading, read failure and retry using dev-only fixture', async () => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.goto('http://127.0.0.1:5173/tests/browser/harness.html')
    await page.getByText('正在读取演示数据…', { exact: true }).waitFor()
    await page.getByRole('heading', { name: '暂时无法读取', exact: true }).waitFor()
    await screenshot('scenario-read-failure')
    await page.getByRole('button', { name: '重新读取', exact: true }).click(); await readyPage()
    await page.getByRole('heading', { name: '看看商家们的表现', exact: true }).waitFor()
  })
  await check('external updates, stale price rejection and safe submission retry', async () => {
    await nav('商品推荐', '发现适合你的好物')
    await page.evaluate(() => window.testHost.controls.updateProduct('p1', { stock: 2, priceCents: 9900 }))
    await readyPage()
    const card = page.locator('.product-card').filter({ has: page.getByRole('heading', { name: '陶瓷随行杯', exact: true }) })
    await card.getByText('剩余 2 件', { exact: true }).waitFor()
    await card.getByRole('button', { name: '直接购买', exact: true }).click()
    await page.getByRole('dialog', { name: '确认模拟购买' }).waitFor()
    await page.evaluate(() => window.testHost.controls.updateProduct('p1', { priceCents: 10900 }))
    await page.getByRole('button', { name: '确认购买', exact: true }).click()
    await page.getByRole('alert').getByText('价格已变化，请返回详情重新确认。', { exact: true }).waitFor()
    await screenshot('scenario-price-change')
    assert.equal((await page.evaluate(() => window.testBuyer.observe({ view: 'me' }))).orders.length, 0)
    await page.getByRole('button', { name: '返回详情', exact: true }).click()
    await page.getByRole('button', { name: '购买此商品', exact: true }).click()
    await page.getByRole('dialog', { name: '确认模拟购买' }).waitFor()
    await page.evaluate(() => window.testHost.controls.failNext('execute'))
    await page.getByRole('button', { name: '确认购买', exact: true }).click()
    await page.getByRole('alert').getByText('模拟服务暂时不可用', { exact: false }).waitFor()
    assert.equal((await page.evaluate(() => window.testBuyer.observe({ view: 'me' }))).orders.length, 0)
    await page.getByRole('button', { name: '确认购买', exact: true }).click()
    await page.getByRole('heading', { name: '已完成模拟购买', exact: true }).waitFor()
    assert.equal((await page.evaluate(() => window.testBuyer.observe({ view: 'me' }))).orders.length, 1)
    await page.getByRole('button', { name: '查看购买历史', exact: true }).click(); await readyPage()
    await nav('公共交流', '一起聊聊，了解更多')
    await page.evaluate(() => window.testHost.controls.publishMessage('s1', '本轮测试外部消息，不来自当前页面提交。'))
    await page.getByRole('log').getByText('本轮测试外部消息，不来自当前页面提交。', { exact: true }).waitFor()
    await screenshot('scenario-external-message')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.evaluate(() => window.testHost.controls.publishMessage('s1', 'A'.repeat(500)))
    await readyPage(); await noOverflow()
  })
  assert.deepEqual(errors, [], 'Browser runtime errors')
  await writeFile(path.join(evidence, 'browser-results.json'), JSON.stringify({ checkedAt: new Date().toISOString(), browser: await browser.version(), viewport: ['1440x1000', '390x844', '320x740'], passed: steps, errors, status: 'passed', scope: 'Local demo only; no user visual acceptance' }, null, 2) + '\n')
} catch (error) {
  await writeFile(path.join(evidence, 'browser-results.json'), JSON.stringify({ checkedAt: new Date().toISOString(), status: 'failed', passed: steps, errors, failure: error.stack }, null, 2) + '\n')
  throw error
} finally {
  await browser?.close()
  await stopOwnedServer()
  await writeFile(path.join(root, '.local/browser-vite.log'), log)
}
