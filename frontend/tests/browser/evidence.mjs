// Repeated checks write locally; tracked acceptance evidence requires an explicit path.
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

export async function outputDirectories(name) {
  const root = fileURLToPath(new URL('../../..', import.meta.url))
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const local = path.join(root, '.local/verification', name, stamp)
  const evidence = process.env.SALESBENCH_EVIDENCE_DIR
    ? path.resolve(root, process.env.SALESBENCH_EVIDENCE_DIR) : local
  await mkdir(local, { recursive: true })
  await mkdir(evidence, { recursive: true })
  console.log(`Verification output: ${evidence}`)
  return { local, evidence }
}
