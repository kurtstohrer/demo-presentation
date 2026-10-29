// Playwright page actions independent of recording, scenes and narration.
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export function makePageDriver(page, { viewport, speed = 1, baseUrl = '', overlay = '__reviewOverlay' }) {
  const show = (method, args = []) => page.evaluate(
    ([name, method, args]) => window[name]?.[method]?.(...args), [overlay, method, args])
  let cur = { x: viewport.width / 2, y: viewport.height / 2 }
  const t = (ms) => ms / speed
  const base = baseUrl
  const resolveUrl = (u) => (/^[a-z][a-z0-9+.-]*:/i.test(u) ? u : base.replace(/\/$/, '') + u)

  async function target(sel) {
    if (sel && typeof sel === 'object' && 'x' in sel) return { x: sel.x, y: sel.y, box: null }
    const loc = page.locator(sel).first()
    await loc.waitFor({ state: 'visible', timeout: 15000 })
    await loc.scrollIntoViewIfNeeded()
    const box = await loc.boundingBox()
    return { x: box.x + box.width / 2, y: box.y + box.height / 2, box, loc }
  }
  async function moveTo(x, y, ms = 650) {
    const dist = Math.hypot(x - cur.x, y - cur.y)
    const dur = Math.round(Math.min(ms, 250 + dist * 0.5))
    await show('move', [x, y, t(dur)])
    await page.mouse.move(x, y, { steps: Math.max(2, Math.round(dur / 40)) })
    await sleep(t(dur))
    cur = { x, y }
  }
  async function click(sel, opts = {}) {
    const p = await target(sel)
    await moveTo(p.x, p.y)
    await sleep(t(120))
    await show('ripple', [])
    await page.mouse.click(p.x, p.y, { clickCount: opts.count || 1, button: opts.button || 'left' })
    await sleep(t(350))
  }

  const actions = {
    goto: async (url) => { await page.goto(resolveUrl(url), { waitUntil: 'domcontentloaded' }); await show('move', [-200, -200, 0]) },
    // `timeout` (ms) on the action raises the 2-minute default, e.g. to wait out a live background job.
    waitFor: async (sel, a) => page.locator(sel).first().waitFor({ state: 'visible', timeout: a.timeout || 120000 }),
    waitForFunction: async (expr, a) => page.waitForFunction(expr, null, { timeout: a.timeout || 120000, polling: a.polling || 250 }),
    click: async (sel, a) => click(sel, a),
    dblclick: async (sel) => click(sel, { count: 2 }),
    rightClick: async (sel) => click(sel, { button: 'right' }),
    hover: async (sel) => { const p = await target(sel); await moveTo(p.x, p.y); await sleep(t(300)) },
    move: async (pt) => moveTo(pt.x, pt.y, pt.ms),
    fill: async (spec) => {
      await click(spec.selector)
      if (spec.clear !== false) { await page.keyboard.press('ControlOrMeta+a'); await page.keyboard.press('Backspace') }
      await page.keyboard.type(spec.text, { delay: t(spec.delay ?? 55) })
      await sleep(t(250))
    },
    type: async (text, a) => page.keyboard.type(text, { delay: t(a.delay ?? 55) }),
    press: async (key) => { await page.keyboard.press(key); await sleep(t(300)) },
    keyDown: async (key) => page.keyboard.down(key),
    keyUp: async (key) => page.keyboard.up(key),
    scroll: async (spec) => {
      if (spec.selector) { const p = await target(spec.selector); await moveTo(p.x, p.y) }
      const steps = 12
      for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, (spec.y || 0) / steps); await sleep(t(30)) }
      await sleep(t(300))
    },
    drag: async (spec) => {
      const a = await target(spec.from)
      const b = spec.to ? await target(spec.to) : { x: a.x + (spec.dx || 0), y: a.y + (spec.dy || 0) }
      await moveTo(a.x, a.y)
      await page.mouse.down()
      const n = 24
      for (let i = 1; i <= n; i++) {
        const x = a.x + ((b.x - a.x) * i) / n, y = a.y + ((b.y - a.y) * i) / n
        await page.mouse.move(x, y)
        await show('move', [x, y, 0])
        await sleep(t(spec.ms ?? 900) / n)
      }
      await page.mouse.up()
      cur = { x: b.x, y: b.y }
    },
    spotlight: async (spec) => {
      const s = typeof spec === 'string' ? { selector: spec } : spec
      const p = await target(s.selector)
      await show('spotlight', [p.box, s.text || ''])
      await sleep(t(s.ms ?? 1200))
      if (!s.keep) await show('clearSpotlight', [])
    },
    clearSpotlight: async () => show('clearSpotlight', []),
    chapter: async (spec) => {
      const s = typeof spec === 'string' ? { title: spec } : spec
      await show('chapter', [s.title, s.description || ''])
      await sleep(t(s.ms ?? 1800))
      await show('clearChapter', [])
    },
    eval: async (js) => page.evaluate(js),
    wait: async (ms) => sleep(t(Number(ms))),
    screenshot: async () => {},
  }
  return {
    async apply(action) {
      const key = Object.keys(action).find((k) => actions[k])
      if (!key) throw new Error(`unknown ui action: ${JSON.stringify(action)}`)
      await actions[key](action[key], action)
    },
  }
}

