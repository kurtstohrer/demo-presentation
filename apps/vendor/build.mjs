// Copies the scene fonts and browser libraries into the skill, so recording needs no npm.
// Fonts: latin + latin-ext woff2 only, one fonts.css. Captions: an Inter TTF for libass
// (it can't read woff2), converted with fonttools through uv.
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'

const here = path.dirname(fileURLToPath(import.meta.url))
const nm = path.join(here, 'node_modules')
const out = path.resolve(here, '../../skills/demo-presentation/vendor')
const FONTS = [
  ['Inter', 'inter', [400, 600, 800]],
  ['JetBrains Mono', 'jetbrains-mono', [400, 700]],
  ['Caveat', 'caveat', [500, 700]],
]
const SUBSETS = [
  ['latin-ext', 'U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF'],
  ['latin', 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD'],
]

fs.rmSync(out, { recursive: true, force: true })
fs.mkdirSync(path.join(out, 'fonts'), { recursive: true })
const css = []
for (const [family, pkg, weights] of FONTS) {
  for (const w of weights) {
    for (const [subset, range] of SUBSETS) {
      const file = `${pkg}-${subset}-${w}-normal.woff2`
      fs.copyFileSync(path.join(nm, '@fontsource', pkg, 'files', file), path.join(out, 'fonts', file))
      css.push(`@font-face { font-family: '${family}'; font-style: normal; font-display: swap; font-weight: ${w}; src: url(./fonts/${file}) format('woff2'); unicode-range: ${range}; }`)
    }
  }
}
fs.writeFileSync(path.join(out, 'fonts.css'), `/* Built by apps/vendor (fontsource, OFL-1.1). */\n${css.join('\n')}\n`)

const copy = (from, to) => { fs.mkdirSync(path.dirname(path.join(out, to)), { recursive: true }); fs.copyFileSync(path.join(nm, from), path.join(out, to)) }
copy('@xterm/xterm/lib/xterm.js', 'xterm/xterm.js')
copy('@xterm/xterm/css/xterm.css', 'xterm/xterm.css')
copy('@xterm/xterm/LICENSE', 'xterm/LICENSE')
copy('roughjs/bundled/rough.js', 'roughjs/rough.js')
copy('roughjs/LICENSE', 'roughjs/LICENSE')

// Code scenes highlight in the page: window.Shiki.codeToTokens(code, { lang, theme }).
await build({ entryPoints: [path.join(here, 'src/shiki.js')], bundle: true, minify: true, format: 'iife', globalName: 'Shiki',
  outfile: path.join(out, 'shiki.js'), legalComments: 'none', logLevel: 'warning' })

// libass reads TTF/OTF, not woff2; the caption style names family "Inter".
execFileSync('uv', ['run', '--quiet', '--no-project', '--with', 'fonttools[woff]==4.60.1', 'python', '-c',
  'import sys; from fontTools.ttLib import TTFont; f = TTFont(sys.argv[1], recalcTimestamp=False); f.flavor = None; f.save(sys.argv[2])',
  path.join(nm, '@fontsource/inter/files/inter-latin-400-normal.woff2'), path.join(out, 'fonts', 'Inter-Regular.ttf')], { stdio: 'inherit' })
console.log(`vendor: ${out}`)
