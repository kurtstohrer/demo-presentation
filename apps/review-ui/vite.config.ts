// Builds the review UI into the skill, so installing the skill needs no build step.
// `npm run dev` proxies the API to a running `demo serve` on :4177.
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    outDir: fileURLToPath(new URL('../../skills/demo-presentation/ui', import.meta.url)),
    emptyOutDir: true,
    assetsInlineLimit: 0,
  },
  server: { proxy: { '/api': 'http://127.0.0.1:4177', '/files': 'http://127.0.0.1:4177' } },
})
