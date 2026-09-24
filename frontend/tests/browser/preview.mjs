import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import net from 'node:net'
import { chromium } from 'playwright-core'
import { outputDirectories } from './evidence.mjs'

const frontend = fileURLToPath(new URL('../..', import.meta.url))
const root = path.dirname(frontend)
const config = JSON.parse((await readFile(path.join(root, '.local/runtime.json'), 'utf8')).replace(/^\uFEFF/, ''))
const { evidence } = await outputDirectories('preview')
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
  await page.getByRole('heading', { name: '绑定本场角色', exact: true }).waitFor()
  assert.equal(await page.getByLabel('Actor token', { exact: true }).getAttribute('type'), 'password')
  assert.equal((await fetch('http://127.0.0.1:4173/product-placeholder.svg')).status, 200)
  assert.equal(await page.evaluate(() => typeof window.testHost), 'undefined')
  assert.deepEqual(errors, [])
  assert.equal(await page.evaluate(() => typeof window.salesbench), 'undefined')
  await writeFile(path.join(evidence, 'preview-results.json'), JSON.stringify({ checkedAt: new Date().toISOString(), status: 'passed', port: 4173, browser: await browser.version(), entry: 'real-platform-binding', placeholderLoaded: true, testControllerExposed: false, errors, serverStoppedOnExit: true }, null, 2) + '\n')
  console.log('PASS production preview, real binding entry, password field, no demo controller')
} finally {
  await browser?.close()
  if (server.exitCode === null) {
    if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill.exe', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
    else server.kill('SIGTERM')
  }
}
