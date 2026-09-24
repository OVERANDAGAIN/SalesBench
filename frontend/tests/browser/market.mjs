// Real production Vue, four isolated browser contexts, real HTTP + PostgreSQL.
// No route mocking, DOM state injection, direct economic API calls or token logging.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import net from 'node:net'
import { chromium } from 'playwright-core'
import { outputDirectories } from './evidence.mjs'

const frontend = fileURLToPath(new URL('../..', import.meta.url)), root = path.dirname(frontend)
const readJSON = async file => JSON.parse((await readFile(file, 'utf8')).replace(/^\uFEFF/, ''))
const config = await readJSON(path.join(root, '.local/runtime.json'))
const platform = await readJSON(path.join(root, '.local/platform.json'))
const { evidence, local } = await outputDirectories('market')
process.env.TEMP = path.join(config.cache, 'browser-temp'); process.env.TMP = process.env.TEMP
await mkdir(process.env.TEMP, { recursive: true })
function platformCommand(task, args = []) {
  const result = spawnSync('pwsh', ['-NoProfile', '-File', path.join(root, 'scripts/platform.ps1'), task, ...args], { cwd: root, windowsHide: true, encoding: 'utf8', timeout: 60000 })
  assert.equal(result.status, 0, `Platform command ${task} failed; output intentionally not logged`)
  return result.stdout
}
async function available(port) { await new Promise((resolve, reject) => { const p = net.createServer(); p.once('error', () => reject(new Error(`${port} occupied; existing process preserved`))); p.listen(port, '127.0.0.1', () => p.close(resolve)) }) }
await available(8000); await available(4173)
const created = JSON.parse(platformCommand('create-manual'))
await writeFile(path.join(local, 'browser-session.json'), JSON.stringify(created, null, 2))
const secrets = [platform.admin_token, ...await Promise.all(created.actors.map(async actor => (await readJSON(path.join(created.binding_directory, actor + '.json'))).actor_token))]
const steps = [], network = new Map(), errors = [], pages = {}
let api, preview, browser
async function waitFor(work, label, attempts = 100) { for (let i = 0; i < attempts; i++) { if (await work()) return; await new Promise(r => setTimeout(r, 150)) } throw new Error(`Timed out: ${label}`) }
async function stop(child) {
  if (!child || child.exitCode !== null) return
  if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
  else { child.kill('SIGTERM'); await new Promise(resolve => child.on('exit', resolve)) }
}
async function startApi() {
  api = spawn(path.join(root, 'backend/.venv/Scripts/python.exe'), ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--workers', '1'],
    { cwd: path.join(root, 'backend'), windowsHide: true, stdio: 'ignore', env: { ...process.env, SALESBENCH_DATABASE_URL: platform.database_url, SALESBENCH_ADMIN_TOKEN: platform.admin_token, SALESBENCH_AUTO_RUN: '1' } })
  await waitFor(async () => { try { return (await fetch('http://127.0.0.1:8000/health')).ok } catch { return false } }, 'API ready')
}
async function version(page, number) { await waitFor(async () => (await page.getByTestId('publication').textContent({ timeout: 300 }).catch(() => '')) === `Publication ${number}`, `publication ${number}`, 50) }
async function allVersion(number) { for (const page of Object.values(pages)) await version(page, number) }
async function addSeller(page, type, values = {}) {
  await page.getByLabel('Seller 动作类型', { exact: true }).selectOption(type)
  for (const [label, value] of Object.entries(values)) {
    const input = page.getByLabel(label, { exact: true })
    if (label === '采购报价' || label === '在售状态') await input.selectOption(String(value))
    else await input.fill(String(value))
  }
  await page.getByRole('button', { name: '加入有序批次', exact: true }).click()
}
async function submit(page) { await page.getByRole('button', { name: '提交本轮批次', exact: true }).click() }
async function waitAction(page) { await page.getByRole('button', { name: '明确 Wait / 不行动', exact: true }).click(); await submit(page) }
async function nav(page, title) { await page.getByRole('navigation', { name: '主导航' }).getByRole('button', { name: title, exact: true }).click() }
async function buy(page, listing) {
  await nav(page, '商品推荐')
  const card = page.locator('.product-card').filter({ has: page.locator('.variant', { hasText: listing }) })
  await card.getByRole('button', { name: '直接购买', exact: true }).click()
  await page.getByRole('dialog', { name: '确认购买意图' }).getByRole('button', { name: '加入本轮批次', exact: true }).click()
}
async function message(page, channel, text) {
  await nav(page, channel === 'public' ? '公共交流' : '私聊')
  await page.getByRole('button', { name: `Seller A${channel === 'public' ? '讨论区' : '私聊'}`, exact: true }).click()
  await page.getByLabel(channel === 'public' ? '公开消息内容' : '私聊消息内容', { exact: true }).fill(text)
  await page.getByRole('button', { name: '加入本轮消息', exact: true }).click()
}
async function shot(page, name) {
  const html = await page.content()
  assert(!secrets.some(secret => html.includes(secret)), 'Credential must never appear in page content')
  assert(!secrets.some(secret => page.url().includes(secret)), 'Credential must never appear in URL')
  await page.screenshot({ path: path.join(evidence, name + '.png'), fullPage: true })
}
async function check(label, run) { await run(); steps.push(label); console.log('PASS ' + label) }
try {
  await startApi()
  console.log('READY local API')
  preview = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4173', '--strictPort'], { cwd: frontend, windowsHide: true, stdio: 'ignore' })
  await waitFor(async () => { try { return (await fetch('http://127.0.0.1:4173')).ok } catch { return false } }, 'production preview')
  browser = await chromium.launch({ executablePath: config.browser, headless: true, chromiumSandbox: true })
  console.log('READY browser')
  for (const actor of created.actors) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN' })
    const page = pages[actor] = await context.newPage(); page.setDefaultTimeout(12000)
    page.on('pageerror', error => errors.push(error.message))
    page.on('requestfailed', request => { if (request.url().includes('/api/v1/')) console.log('TRANSPORT ' + new URL(request.url()).pathname + ' ' + request.failure()?.errorText) })
    page.on('response', async response => {
      const url = new URL(response.url())
      if (!url.pathname.startsWith('/api/v1/')) return
      const key = `${response.request().method()} ${url.pathname.split(created.session_id).join('{session}')} ${response.status()}`
      network.set(key, (network.get(key) ?? 0) + 1)
      assert(!secrets.some(secret => response.url().includes(secret)), 'Token URL leakage')
    })
    await page.goto('http://127.0.0.1:4173')
    await page.getByLabel('导入角色文件', { exact: true }).setInputFiles(path.join(created.binding_directory, actor + '.json'))
    await page.waitForSelector('[data-testid="wave-panel"], [role="alert"]')
    if (await page.getByRole('alert').count()) throw new Error('Binding failed: ' + await page.getByRole('alert').first().textContent())
    await version(page, 0)
    console.log('BOUND ' + actor)
    assert.equal(await page.evaluate(() => typeof window.testHost), 'undefined')
    assert.equal(await page.evaluate(() => typeof window.salesbench), 'undefined')
  }
  const a = pages['seller-a'], b = pages['seller-b'], one = pages['buyer-1'], two = pages['buyer-2']
  await check('four isolated actor bindings; real OpenAPI available', async () => {
    assert((await fetch('http://127.0.0.1:8000/docs')).ok)
    const openapi = await (await fetch('http://127.0.0.1:8000/openapi.json')).json()
    assert(openapi.paths['/api/v1/sessions/{session_id}/actions'])
    await shot(a, 'seller-procurement')
  })
  await check('Round procurement waits for both Sellers', async () => {
    await addSeller(a, 'procure', { '采购报价': 'cups', '采购数量': 1 }); await submit(a)
    await a.getByText('本人已提交', { exact: false }).waitFor(); await version(one, 0)
    await addSeller(b, 'procure', { '采购报价': 'cups', '采购数量': 3 }); await submit(b); await allVersion(1)
  })
  await check('Seller publication only after both ordered batches; Buyers see Listings', async () => {
    await addSeller(a, 'create_listing', { 'Listing ID': 'cup', 'Product ID': 'cup', '售价（整数分）': 300, '销售描述': 'Seller A 首发陶瓷杯' }); await submit(a)
    await version(one, 1)
    await addSeller(b, 'create_listing', { 'Listing ID': 'cup', 'Product ID': 'cup', '售价（整数分）': 500, '销售描述': 'Seller B 现货陶瓷杯' }); await submit(b); await allVersion(2)
    await nav(one, '商品推荐'); assert.equal(await one.locator('.product-card').count(), 2)
    await shot(one, 'buyer-products')
  })
  await check('public + private + purchase batch is pending until other Buyer submits', async () => {
    await message(one, 'public', '杯子可以清洗吗？公开验收消息')
    await message(one, 'private', '仅 Buyer 1 与 Seller A 可见的私聊')
    await buy(one, 'seller-a/cup'); assert.equal(await one.locator('.batch-list li').count(), 3)
    await buy(two, 'seller-a/cup')
    await submit(one); await one.getByText('本人已提交', { exact: false }).waitFor()
    await version(two, 2); await shot(one, 'buyer-pending')
    await submit(two); await allVersion(3)
    const report = JSON.parse(platformCommand('inspect', ['-SessionId', created.session_id]))
    assert.equal(report.orders.length, 1)
    assert(report.receipts.some(r => r.outcome_codes.includes('OUT_OF_STOCK')))
    await shot(pages[report.orders[0].buyer_id === 'buyer-1' ? 'buyer-2' : 'buyer-1'], 'buyer-failed-purchase')
  })
  await check('next Tick Seller feedback and private isolation; price/content visible to same Tick Buyers', async () => {
    await a.getByText('仅 Buyer 1 与 Seller A 可见的私聊', { exact: true }).waitFor()
    assert(!(await b.locator('.seller-messages').allTextContents()).join(' ').includes('仅 Buyer 1'))
    await shot(a, 'seller-feedback')
    await addSeller(a, 'price', { 'Listing ID': 'cup', '售价（整数分）': 400 })
    await addSeller(a, 'description', { 'Listing ID': 'cup', '销售描述': '下一 Tick 已更新销售描述' })
    await addSeller(a, 'send_public', { 'Seller 消息内容': '可以清洗，这是 Seller A 的公开回复' }); await submit(a)
    await addSeller(b, 'send_private', { '私人消息接收者': 'buyer-2', 'Seller 消息内容': '仅 Buyer 2 与 Seller B 可见的回复' }); await submit(b); await allVersion(4)
    await nav(one, '商品推荐')
    const card = one.locator('.product-card').filter({ has: one.locator('.variant', { hasText: 'seller-a/cup' }) })
    assert((await card.textContent()).includes('4'))
    await card.getByRole('button', { name: '查看陶瓷杯详情', exact: true }).click()
    await one.getByText('报价 v2', { exact: true }).waitFor(); await one.getByText('内容 v2', { exact: true }).waitFor()
    await one.getByRole('button', { name: '继续浏览', exact: true }).click()
    await nav(two, '私聊'); await two.getByRole('button', { name: 'Seller A私聊', exact: true }).click()
    assert(!(await two.getByRole('log').textContent()).includes('仅 Buyer 1'))
    await nav(one, '私聊'); await one.getByRole('button', { name: 'Seller B私聊', exact: true }).click()
    assert(!(await one.getByRole('log').textContent()).includes('仅 Buyer 2'))
    await one.getByRole('button', { name: 'Seller A私聊', exact: true }).click(); await shot(one, 'buyer-private')
    await nav(one, '公共交流'); await one.getByRole('button', { name: 'Seller A讨论区', exact: true }).click(); await shot(one, 'buyer-public')
  })
  await check('direct purchase versus explicit non-purchase; active/content revisions preserve protocol', async () => {
    await buy(one, 'seller-b/cup'); await submit(one)
    await nav(two, '商品推荐'); await two.locator('.product-card').first().getByRole('button', { name: '查看陶瓷杯详情', exact: true }).click()
    await two.getByRole('button', { name: '暂不购买', exact: true }).click(); await submit(two); await allVersion(5)
    await addSeller(a, 'active', { 'Listing ID': 'cup', '在售状态': 'false' }); await addSeller(a, 'active', { '在售状态': 'true' }); await submit(a)
    await waitAction(b); await allVersion(6)
    await waitAction(one); await waitAction(two); await allVersion(8)
  })
  await check('browser reload restores committed balance/orders; backend and PostgreSQL restart continue same session', async () => {
    await nav(one, '我的'); await shot(one, 'buyer-account')
    await one.reload(); await version(one, 8); await nav(one, '我的')
    const before = JSON.parse(platformCommand('inspect', ['-SessionId', created.session_id]))
    await stop(api); api = null
    platformCommand('pg-stop')
    await one.getByText('连接中断 · 数据可能过期', { exact: true }).waitFor()
    assert(!(await one.content()).includes('本地演示 · Vue'))
    platformCommand('pg-start'); await startApi(); await allVersion(8)
    await one.getByText('服务已连接', { exact: true }).waitFor()
    const after = JSON.parse(platformCommand('inspect', ['-SessionId', created.session_id]))
    assert.equal(before.journal.state_digest, after.journal.state_digest)
    assert.deepEqual(before.orders, after.orders)
    await addSeller(a, 'procure', { '采购数量': 2 }); await submit(a); await waitAction(b); await allVersion(9)
  })
  await check('post-restart Round continues; two Buyers consume available shared stock', async () => {
    await addSeller(a, 'price', { '售价（整数分）': 450 }); await submit(a); await waitAction(b); await allVersion(10)
    await buy(one, 'seller-a/cup'); await buy(two, 'seller-a/cup'); await submit(one); await submit(two); await allVersion(11)
    for (const [sellerVersion, buyerVersion] of [[12, 13], [14, 16]]) {
      await waitAction(a); await waitAction(b); await allVersion(sellerVersion)
      await waitAction(one); await waitAction(two); await allVersion(buyerVersion)
    }
  })
  await check('five Buyer pages, Seller final state, H5 layout and PostgreSQL inspection', async () => {
    for (const [label, file] of [['排行榜', 'buyer-ranking'], ['我的', 'buyer-final-account']]) { await nav(one, label); await shot(one, file) }
    await shot(a, 'seller-final')
    await one.setViewportSize({ width: 390, height: 844 }); await nav(one, '商品推荐')
    assert(await one.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'H5 horizontal overflow')
    await shot(one, 'h5-buyer-products')
    const report = JSON.parse(platformCommand('inspect', ['-SessionId', created.session_id]))
    assert.equal(report.runtime.status, 'completed'); assert.equal(report.runtime.engine_step, 2); assert.equal(report.current_publication, 16)
    assert.equal(report.orders.length, 4); assert.equal(report.table_counts.publications, 17)
    assert(report.table_counts.action_receipts > 0); assert(report.table_counts.batch_receipts > 0)
    assert.equal(report.receipts.filter(r => r.status === 'pending').length, 0)
    assert([...network.keys()].some(k => k.startsWith('POST ') && k.endsWith('202')))
    assert.deepEqual(errors, [])
    const summary = { checkedAt: new Date().toISOString(), status: 'passed', session_id: created.session_id, browser: await browser.version(), steps,
      runtime: report.runtime, table_counts: report.table_counts, orders: report.orders, network: Object.fromEntries(network),
      state_digest: report.journal.state_digest, private_isolation: 'passed', browser_reload: 'passed', api_pg_restart: 'passed', credential_leaks: 0 }
    await writeFile(path.join(evidence, 'results.json'), JSON.stringify(summary, null, 2) + '\n')
    await writeFile(path.join(local, 'inspect.json'), JSON.stringify(report, null, 2))
  })
  const finalSummary = await readJSON(path.join(evidence, 'results.json'))
  finalSummary.steps = steps
  await writeFile(path.join(evidence, 'results.json'), JSON.stringify(finalSummary, null, 2) + '\n')
} catch (error) {
  for (const [actor, page] of Object.entries(pages)) if (await page.getByTestId('wave-panel').count()) await page.screenshot({ path: path.join(local, `failure-${actor}.png`), fullPage: true }).catch(() => {})
  throw error
} finally { await browser?.close(); await stop(preview); await stop(api) }
