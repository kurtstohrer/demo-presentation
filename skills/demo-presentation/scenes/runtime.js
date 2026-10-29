// Shared runtime for HTML scenes. The recorder calls window.__scene.init(scene)
// once and window.__scene.apply(action) for every action; apply resolves when
// the action's animation has finished. window.__speed > 1 compresses animation
// time (used by storyboard previews).
;(function () {
  const handlers = {}
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms / (window.__speed || 1)))

  const THEMES = ['dark', 'light']
  function setTheme(theme) {
    document.documentElement.dataset.theme = THEMES.includes(theme) ? theme : String(theme || '').endsWith('light') ? 'light' : 'dark'
  }

  window.__scene = {
    sleep,
    on(name, fn) {
      handlers[name] = fn
    },
    async init(scene) {
      setTheme(scene.theme)
      if (handlers.init) await handlers.init(scene)
      await document.fonts.ready
    },
    async apply(action) {
      const key = Object.keys(action).find((k) => handlers[k] && k !== 'init')
      if (!key) throw new Error(`unknown action for this scene: ${JSON.stringify(action)}`)
      await handlers[key](action[key], action)
    },
  }

  // Actions every HTML scene understands.
  window.__scene.on('wait', (ms) => sleep(Number(ms) || 0))
  window.__scene.on('heading', (text) => {
    const el = document.querySelector('.scene-title')
    if (!el) return
    el.textContent = text
    el.classList.remove('fade-in')
    void el.offsetWidth
    el.classList.add('fade-in')
    return sleep(450)
  })
  window.__scene.on('subheading', (text) => {
    const el = document.querySelector('.scene-sub')
    if (!el) return
    el.textContent = text
    el.classList.remove('fade-in')
    void el.offsetWidth
    el.classList.add('fade-in')
    return sleep(450)
  })
})()
