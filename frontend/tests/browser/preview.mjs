import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import net from 'node:net'
import { chromium } from 'playwright-core'

const frontend = fileURLToPath(new URL('../..', import.meta.url))
const root = path.dirname(frontend)
const config = JSON.parse(await readFile(path.join(root, '.local/runtime.json'), 'utf8'))
const evidence = path.join(root, 'docs/verification/SB-002B')
await mkdir(evidence, { recursive: true })
process.env.TEMP = path.join(config.cache, 'browser-temp')
process.env.TMP = process.env.TEMP
await mkdir(process.env.TEMP, { recursive: true })
await new Promise((resolve, reject) => {
  const probe = net.createServer()
  probe.once('error', () => reject(new Error('4173 occupied; existing process left untouched')))
  probe.listen(4173, '127.0.0.1', () => probe.close(resolve))
})
let browser
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4173', '--strictPort'], { cwd: frontend, windowsHide: true, stdio: 'ignore' })
try {
  let ready = false
  for (let attempt = 0; attempt < 50; attempt++) {
    try { if ((await fetch('http://127.0.0.1:4173')).ok) { ready = true; break } } catch {}
    await new Promise(resolve => setTimeout(resolve, 200))
  }
  assert(ready, 'Production preview failed to start')
  browser = await chromium.launch({ executablePath: config.browser, headless: true, chromiumSandbox: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN' })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('http://127.0.0.1:4173')
  await page.getByRole('heading', { name: '看看商家们的表现', exact: true }).waitFor()
  await page.getByRole('navigation').getByRole('button', { name: '商品推荐', exact: true }).click()
  await page.getByRole('heading', { name: '发现适合你的好物', exact: true }).waitFor()
  const imageStatus = await page.locator('.product-picture img').evaluateAll(images => images.map(img => img.complete && img.naturalWidth > 0))
  assert.equal(imageStatus.length, 6)
  assert(imageStatus.every(Boolean), 'A production image failed to load')
  assert.equal(await page.evaluate(() => typeof window.testHost), 'undefined')
  assert.deepEqual(errors, [])
  await writeFile(path.join(evidence, 'preview-results.json'), JSON.stringify({ checkedAt: new Date().toISOString(), status: 'passed', port: 4173, browser: await browser.version(), productImagesLoaded: 6, testControllerExposed: false, errors, serverStoppedOnExit: true }, null, 2) + '\n')
  console.log('PASS production preview, Vue navigation, six image resources, no test controller')
} finally {
  await browser?.close()
  if (server.exitCode === null) {
    if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill.exe', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
    else server.kill('SIGTERM')
  }
}
