// Injected into UI-walkthrough pages (addInitScript). Draws a fake cursor,
// click ripples, spotlight and chapter overlays that show up in the screencast.
;(() => {
  if (window.__demoOverlay) return
  const install = () => {
    if (document.getElementById('__demo-layer')) return
    const layer = document.createElement('div')
    layer.id = '__demo-layer'
    layer.innerHTML = `
      <style>
        #__demo-layer { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647; font-family: Inter, system-ui, sans-serif; }
        #__demo-cursor { position: absolute; left: 0; top: 0; width: 34px; height: 34px; transform: translate(-200px, -200px);
          filter: drop-shadow(0 3px 5px rgba(0,0,0,.45)); will-change: transform; }
        .__demo-ripple { position: absolute; width: 56px; height: 56px; margin: -28px 0 0 -28px; border-radius: 50%;
          border: 4px solid #ff8a3d; animation: __demo-ripple 600ms ease-out forwards; }
        @keyframes __demo-ripple { from { transform: scale(.3); opacity: 1; } to { transform: scale(1.4); opacity: 0; } }
        .__demo-spot { position: absolute; border-radius: 12px; box-shadow: 0 0 0 4px #ff8a3d; }
        .__demo-dim { position: absolute; background: rgba(0,0,0,.55); animation: __demo-fade 300ms ease-out both; }
        .__demo-label { position: absolute; max-width: 560px; padding: 14px 20px; border-radius: 10px; background: #ff8a3d; color: #111;
          font-weight: 600; font-size: 24px; line-height: 1.3; box-shadow: 0 12px 30px rgba(0,0,0,.35); }
        .__demo-chapter { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
          gap: 18px; background: rgba(10,12,16,.62); backdrop-filter: blur(10px); color: #fff; animation: __demo-fade 400ms ease-out both; }
        .__demo-chapter h1 { margin: 0; font-size: 72px; font-weight: 800; letter-spacing: -.02em; }
        .__demo-chapter p { margin: 0; font-size: 30px; opacity: .8; }
        @keyframes __demo-fade { from { opacity: 0; } to { opacity: 1; } }
      </style>
      <svg id="__demo-cursor" viewBox="0 0 24 24"><path d="M4 2l15 11.2-6.3.9 3.9 7.4-2.9 1.5-3.9-7.5L4 20z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>`
    document.documentElement.appendChild(layer)
  }
  let pos = { x: -200, y: -200 }
  window.__demoOverlay = {
    install,
    move(x, y, ms) {
      install()
      const c = document.getElementById('__demo-cursor')
      c.style.transition = ms ? `transform ${ms}ms cubic-bezier(.45,.05,.25,1)` : 'none'
      c.style.transform = `translate(${x - 6}px, ${y - 3}px)`
      pos = { x, y }
    },
    ripple() {
      install()
      const r = document.createElement('div')
      r.className = '__demo-ripple'
      r.style.left = `${pos.x}px`
      r.style.top = `${pos.y}px`
      document.getElementById('__demo-layer').appendChild(r)
      setTimeout(() => r.remove(), 700)
    },
    spotlight(rect, text) {
      install()
      const layer = document.getElementById('__demo-layer')
      this.clearSpotlight()
      const pad = 10
      const x = rect.x - pad, y = rect.y - pad, w = rect.width + pad * 2, h = rect.height + pad * 2
      // Four dim panels around the target (giant box-shadows/outlines get dropped on some pages).
      for (const [l, t, pw, ph] of [[0, 0, innerWidth, Math.max(0, y)], [0, y + h, innerWidth, innerHeight], [0, y, Math.max(0, x), h], [x + w, y, innerWidth, h]]) {
        const d = document.createElement('div')
        d.className = '__demo-dim'
        Object.assign(d.style, { left: `${l}px`, top: `${t}px`, width: `${pw}px`, height: `${ph}px` })
        layer.appendChild(d)
      }
      const s = document.createElement('div')
      s.className = '__demo-spot'
      Object.assign(s.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` })
      layer.appendChild(s)
      if (text) {
        const l = document.createElement('div')
        l.className = '__demo-label'
        l.textContent = text
        layer.appendChild(l)
        const below = rect.y + rect.height + 28
        const above = rect.y - 120
        let left = Math.min(Math.max(20, rect.x), innerWidth - 600)
        let top
        if (below + 120 < innerHeight) top = below
        else if (above > 20) top = above
        else {
          // Tall element (e.g. a full-height pane): put the label beside it.
          top = rect.y + rect.height / 2 - 40
          left = rect.x > 640 ? rect.x - 600 : Math.min(rect.x + rect.width + 28, innerWidth - 600)
        }
        Object.assign(l.style, { left: `${left}px`, top: `${top}px` })
      }
    },
    clearSpotlight() {
      document.querySelectorAll('#__demo-layer .__demo-spot, #__demo-layer .__demo-dim, #__demo-layer .__demo-label').forEach((n) => n.remove())
    },
    chapter(title, description) {
      install()
      const c = document.createElement('div')
      c.className = '__demo-chapter'
      c.innerHTML = '<h1></h1><p></p>'
      c.querySelector('h1').textContent = title
      c.querySelector('p').textContent = description || ''
      document.getElementById('__demo-layer').appendChild(c)
      return c
    },
    clearChapter() {
      document.querySelectorAll('#__demo-layer .__demo-chapter').forEach((n) => n.remove())
    },
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install)
  else install()
})()
