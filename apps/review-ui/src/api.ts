import { ref } from 'vue'

export interface Beat { say?: string; do?: Array<Record<string, unknown>>; [k: string]: unknown }
export interface Scene { id: string; type: string; title?: string; beats: Beat[]; [k: string]: unknown }
export interface Script { title: string; voice?: string; theme?: string; scenes: Scene[]; [k: string]: unknown }
export interface Reply { author: string; text: string; at?: string }
export interface Comment { id: string; t: number | null; key: string | null; region: Region | null; text: string; status: string; author: string; version: number; replies?: Reply[] }
export interface Decision { id: string; scope: 'run' | 'scene' | 'beat'; key: string | null; decision: 'approve' | 'changes'; note: string; version: number; state: string; reply?: string }
export interface Review { status: string; version: number; decisions: Decision[]; comments: Comment[] }
export interface Region { x: number; y: number; w: number; h: number }
export interface Word { w: string; s: number; e: number }
export interface FinalBeat { key: string; index: number; start: number; end: number; say: string; audio: number; words?: Word[] }
export interface FinalScene { id: string; type: string; title: string; start: number; end: number; beats: FinalBeat[] }
export interface Final { title: string; duration: number; scenes: FinalScene[]; version?: number }
export interface Job { kind: string; scenes: string[]; state: string; started: number; ended: number | null; code: number | null; seq: number; lines: string[] }
export interface Stale { narration: string[]; record: string[]; storyboard: string[]; stitch: boolean }
export interface Run {
  name: string; project: string; script: Script; review: Review; audio: Record<string, { duration: number }>; final: Final | null
  hasFinal: boolean; videoVersion: string; frames: string[]; stale: Stale; job: Job | null; fingerprint: string; versions: Array<{ version: number }>
  /** The project pronunciation library; it wins over script.lexicon. */
  library: Record<string, string>
}
export type Lexicon = Record<string, string>
export interface RunSummary {
  name: string; title: string; status: string; version: number; scenes: number; duration: number | null
  openComments: number; openDecisions: number; updated: number; thumb: string | null; job: Job | null
}

export async function api<T = unknown>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, { method, headers: body ? { 'content-type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const d = (data as { detail?: unknown }).detail
    const msg = typeof d === 'string' ? d : (d as { problems?: string[] })?.problems?.join('\n') ?? `${res.status} ${res.statusText}`
    throw new Error(msg)
  }
  return data as T
}
export const runUrl = (name: string, path = '') => `/api/runs/${encodeURIComponent(name)}${path}`

export const fmt = (t: number | null | undefined) => {
  if (t == null || Number.isNaN(t)) return '–'
  const m = Math.floor(t / 60)
  return `${m}:${(t - m * 60).toFixed(1).padStart(4, '0')}`
}
export const ago = (ts: number) => {
  const s = Date.now() / 1000 - ts
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}
export const estimate = (say?: string) => {
  const n = (say ?? '').trim().split(/\s+/).filter(Boolean).length
  return n ? n / 2.6 + 0.3 : 0
}
export const actionSummary = (a: Record<string, unknown>): [string, string] => {
  const k = Object.keys(a).find(x => !x.startsWith('__')) ?? '?'
  const v = a[k] as unknown
  const o = v && typeof v === 'object' ? (v as Record<string, unknown>) : null
  const val = o ? String(o.text ?? o.selector ?? o.title ?? o.code ?? o.id ?? JSON.stringify(o)) : String(v)
  return [k, val.slice(0, 90)]
}

/** The lexicon key for a transcript word: surrounding punctuation stripped ("CLI," -> "CLI"). */
export const wordKey = (w: string) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
/** Effective lexicon for narration: the script's entries overlaid by the library. */
export const lexiconOf = (run: Run): Lexicon => ({ ...((run.script.lexicon as Lexicon | undefined) ?? {}), ...run.library })

/** Speak text through the server's Kokoro with the given lexicon; resolves when playback ends. */
let speaking: HTMLAudioElement | null = null
export async function speak(text: string, voice: string | undefined, lexicon: Lexicon, speed?: number) {
  const res = await fetch('/api/pronounce', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text, voice, lexicon, speed }) })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `${res.status} ${res.statusText}`)
  const url = URL.createObjectURL(await res.blob())
  speaking?.pause()
  const audio = speaking = new Audio(url)
  await new Promise<void>(resolve => {
    audio.onended = audio.onerror = audio.onpause = () => { URL.revokeObjectURL(url); resolve() }
    audio.play().catch(() => resolve())
  })
}

export const STATUS: Record<string, [string, 'neutral' | 'accent' | 'a' | 'b' | 'x' | 'y']> = {
  draft: ['Draft', 'neutral'],
  'storyboard-review': ['Storyboard review', 'x'],
  'approved-to-record': ['Approved to record', 'accent'],
  'video-review': ['Video review', 'b'],
  done: ['Done', 'y'],
}

/** One toast at a time, cleared after a few seconds. */
export const toastText = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
export function toast(text: string) {
  toastText.value = text
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastText.value = '' }, 3500)
}

/** Hash routes: #/ and #/run/<name>/<tool>. */
export const hash = ref(location.hash || '#/')
addEventListener('hashchange', () => { hash.value = location.hash || '#/' })
