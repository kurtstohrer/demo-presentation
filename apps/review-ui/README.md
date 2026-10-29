# review-ui

The review UI for the demo-presentation skill: Vue 3 + Vite, a handful of local
components in `src/components/` (on reka-ui) and one `src/tokens.css`.

```bash
npm ci
npm run dev      # http://localhost:5173, API proxied to a running `demo serve` on :4177
npm run build    # typecheck, then build into skills/demo-presentation/ui (commit the result)
```

The skill ships the built `ui/`, so installing it needs no build step.
`python3 scripts/check.py` fails when the committed build is not what this source produces.
