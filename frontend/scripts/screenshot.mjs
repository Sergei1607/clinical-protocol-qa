// Dev helper: drive the running app with headless Chrome and save a screenshot.
// Needs the dev server up (npm run dev) and the backend up. Points at the local
// Chrome install rather than downloading a browser (puppeteer-core, no bundle).
//
//   node scripts/screenshot.mjs out.png "your question here" [no-expand]
//
// Third arg "no" skips expanding the Sources block (for refusal answers that
// have no sources).

import { existsSync } from 'node:fs'
import puppeteer from 'puppeteer-core'

const CHROME_CANDIDATES = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
]
const CHROME = CHROME_CANDIDATES.find(existsSync)
if (!CHROME) throw new Error('No Chrome/Edge found; set an executablePath in screenshot.mjs')

const URL = process.env.APP_URL || 'http://localhost:5173'
const OUT = process.argv[2] || 'screenshot.png'
const QUESTION = process.argv[3] || 'What is the primary endpoint of this study?'
const EXPAND = process.argv[4] !== 'no'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'shell',
  args: ['--no-sandbox', '--window-size=1200,1600'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1200, height: 1600, deviceScaleFactor: 2 })
page.on('pageerror', (e) => console.log('PAGE EXCEPTION:', e.message))

await page.goto(URL, { waitUntil: 'networkidle0', timeout: 30000 })
await page.waitForSelector('textarea')
await page.type('textarea', QUESTION)
await page.keyboard.press('Enter')

await page.waitForFunction(
  () =>
    !document.body.innerText.includes('searching the protocol') &&
    document.querySelectorAll('div.space-y-5 > div').length >= 2,
  { timeout: 120000 },
)
await sleep(600)

if (EXPAND) {
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find((b) => /^Sources \(/.test(b.textContent || ''))
    btn?.click()
  })
  await sleep(700)
}

await page.evaluate(() => window.scrollTo(0, 0))
await page.screenshot({ path: OUT, fullPage: true })
console.log('wrote', OUT)
await browser.close()
