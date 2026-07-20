'use client'

import { useEffect, useState } from 'react'
import { ArrowRight, BarChart3, Scale, Sparkles } from 'lucide-react'
import { useRouter } from 'next/navigation'

// ── Data — interleaved income/expense for visual variety ─────────────────────
const TRANSACTIONS = [
  { contact: 'Westfield Corp',            amount: 18000, category: 'Sales',                   income: true  },
  { contact: 'ADP Payroll Services',       amount: 12500, category: 'Wages & Salaries',        income: false },
  { contact: 'Apex Solutions Ltd',         amount: 22000, category: 'Sales',                   income: true  },
  { contact: 'Metro Office Supplies',      amount: 4000,  category: 'Office Expenses',         income: false },
  { contact: 'Maddox Publishing Group',    amount: 11700, category: 'Sales',                   income: true  },
  { contact: 'Commercial Property Group',  amount: 3500,  category: 'Rent',                    income: false },
  { contact: 'Blue Mountain Consulting',   amount: 25000, category: 'Sales',                   income: true  },
  { contact: 'TechStream Pty Ltd',         amount: 490,   category: 'Subscriptions',           income: false },
  { contact: 'Pacific Trade Partners',     amount: 26500, category: 'Sales',                   income: true  },
  { contact: 'Digital Marketing Agency',   amount: 1500,  category: 'Advertising',             income: false },
  { contact: 'Apex Solutions Ltd',         amount: 28000, category: 'Sales',                   income: true  },
  { contact: 'Peak Advisory Services',     amount: 2400,  category: 'Consulting & Accounting', income: false },
  { contact: 'Northern Logistics',         amount: 7800,  category: 'Sales',                   income: true  },
  { contact: 'Harrington & Associates',    amount: 13600, category: 'Sales',                   income: true  },
]

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmt(n: number) {
  return n.toLocaleString('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })
}

// Seeded deterministic random — no hydration mismatch
function sr(seed: number): number {
  const s = Math.sin(seed * 9301 + 49297) * 233280
  return s - Math.floor(s)
}

// ── Report generation ─────────────────────────────────────────────────────────
type ReportTarget = 'profit-loss' | 'balance-sheet'
type Phase = 'scanning' | 'classified' | 'done'

const REPORTS: Record<ReportTarget, {
  title: string
  description: string
  href: string
  icon: typeof BarChart3
  accent: string
}> = {
  'profit-loss': {
    title: 'Profit & Loss',
    description: 'Generate a performance report covering revenue, expenses and net profit.',
    href: '/profit-loss',
    icon: BarChart3,
    accent: 'emerald',
  },
  'balance-sheet': {
    title: 'Balance Sheet',
    description: 'Generate a position report covering assets, liabilities and equity.',
    href: '/balance-sheet',
    icon: Scale,
    accent: 'violet',
  },
}

const CLASSIFY_DELAY_MS = 650
const PROGRESS_INTERVAL_MS = 1000
const REDIRECT_DELAY_MS = 800

// ── SVG constants ─────────────────────────────────────────────────────────────
const OX = 500   // orb centre X
const OY = 290   // orb centre Y

// ── Pre-computed static geometry ─────────────────────────────────────────────

// Star field
const STARS = Array.from({ length: 70 }, (_, i) => ({
  x:  (sr(i * 13)     * 960 + 20).toFixed(1),
  y:  (sr(i * 13 + 1) * 540 + 20).toFixed(1),
  r:  (0.4 + sr(i * 13 + 2) * 1.2).toFixed(1),
  op: (0.12 + sr(i * 13 + 3) * 0.38).toFixed(2),
}))

// Radar wedge path (30° sector, radius 112)
const RAD_END_X = (OX + 112 * Math.cos(Math.PI / 6)).toFixed(1)
const RAD_END_Y = (OY + 112 * Math.sin(Math.PI / 6)).toFixed(1)
const RADAR_PATH = `M ${OX} ${OY} L ${OX + 112} ${OY} A 112 112 0 0 1 ${RAD_END_X} ${RAD_END_Y} Z`

// 12 ray spokes (inner radius 54, outer 145)
const RAYS = Array.from({ length: 12 }, (_, i) => {
  const a = (i * Math.PI * 2) / 12
  return {
    x1: (OX + 54  * Math.cos(a)).toFixed(1),
    y1: (OY + 54  * Math.sin(a)).toFixed(1),
    x2: (OX + 145 * Math.cos(a)).toFixed(1),
    y2: (OY + 145 * Math.sin(a)).toFixed(1),
  }
})

// Ambient orbital dots
const ORBITERS = [
  { r: 102, dur: '14s', start: 0,   size: 2.5, color: '#818cf8', op: 0.6  },
  { r: 102, dur: '14s', start: 180, size: 2,   color: '#818cf8', op: 0.38 },
  { r: 78,  dur: '9s',  start: 90,  size: 2,   color: '#34d399', op: 0.55 },
  { r: 78,  dur: '9s',  start: 270, size: 1.5, color: '#34d399', op: 0.3  },
  { r: 122, dur: '20s', start: 45,  size: 1.5, color: '#c4b5fd', op: 0.42 },
  { r: 122, dur: '20s', start: 225, size: 1.2, color: '#c4b5fd', op: 0.25 },
  { r: 90,  dur: '11s', start: 135, size: 1.8, color: '#a78bfa', op: 0.35 },
]

// ── Particle generation ───────────────────────────────────────────────────────
interface Particle { id: number; path: string; dur: number; delay: number; color: string }

function makeParticles(txIdx: number, income: boolean, count = 10): Particle[] {
  const color = income ? '#34d399' : '#a78bfa'
  return Array.from({ length: count }, (_, i) => {
    const s    = txIdx * 200 + i
    const sx   = 40  + sr(s)       * 170
    const sy   = 60  + sr(s + 1)   * 460
    const cp1x = sx  + 80 + sr(s + 2) * 80
    const cp1y = sy  + (OY - sy)   * 0.4 + (sr(s + 3) - 0.5) * 60
    const cp2x = OX  - 60 - sr(s + 4) * 60
    const cp2y = OY  + (sr(s + 5)  - 0.5) * 80
    return {
      id:    i,
      path:  `M ${sx.toFixed(0)} ${sy.toFixed(0)} C ${cp1x.toFixed(0)} ${cp1y.toFixed(0)} ${cp2x.toFixed(0)} ${cp2y.toFixed(0)} ${OX} ${OY}`,
      dur:   0.85,
      delay: i * 0.08,
      color,
    }
  })
}

// ── Component ────────────────────────────────────────────────────────────────
export default function AIInsightsPage() {
  const router = useRouter()
  const [reportTarget, setReportTarget] = useState<ReportTarget | null>(null)
  const [phase,    setPhase]    = useState<Phase>('scanning')
  const [txIdx,    setTxIdx]    = useState(0)
  const [litCount, setLitCount] = useState(0)

  useEffect(() => {
    if (!reportTarget || litCount >= TRANSACTIONS.length) return

    const classifyTimer = window.setTimeout(() => {
      setPhase('classified')
    }, CLASSIFY_DELAY_MS)

    const progressTimer = window.setTimeout(() => {
      const nextCount = Math.min(litCount + 2, TRANSACTIONS.length)
      setLitCount(nextCount)
      setTxIdx(Math.max(0, nextCount - 1))
      setPhase(nextCount === TRANSACTIONS.length ? 'done' : 'scanning')
    }, PROGRESS_INTERVAL_MS)

    return () => {
      window.clearTimeout(classifyTimer)
      window.clearTimeout(progressTimer)
    }
  }, [litCount, reportTarget])

  useEffect(() => {
    if (!reportTarget || phase !== 'done') return

    const redirectTimer = window.setTimeout(() => {
      router.push(REPORTS[reportTarget].href)
    }, REDIRECT_DELAY_MS)

    return () => window.clearTimeout(redirectTimer)
  }, [phase, reportTarget, router])

  function startGeneration(target: ReportTarget) {
    setPhase('scanning')
    setTxIdx(0)
    setLitCount(0)
    setReportTarget(target)
  }

  if (!reportTarget) {
    return (
      <div className="relative flex h-full items-center justify-center overflow-hidden bg-[#03060f] px-6 py-10 text-white">
        <div
          className="absolute inset-0 opacity-70"
          style={{
            backgroundImage: [
              'radial-gradient(circle at 50% 28%, rgba(91, 33, 182, 0.3), transparent 36%)',
              'linear-gradient(rgba(26, 46, 80, 0.22) 1px, transparent 1px)',
              'linear-gradient(90deg, rgba(26, 46, 80, 0.22) 1px, transparent 1px)',
            ].join(', '),
            backgroundSize: 'auto, 48px 48px, 48px 48px',
          }}
        />

        <div className="relative z-10 w-full max-w-3xl">
          <div className="mb-10 text-center">
            <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-violet-400/25 bg-violet-500/10 text-violet-300 shadow-[0_0_45px_rgba(124,58,237,0.22)]">
              <Sparkles className="h-5 w-5" />
            </div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-violet-300/80">AI Insights</p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Choose a report to generate</h1>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-400">
              Select the financial report you want to prepare. We&apos;ll simulate the analysis and open the completed report automatically.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {(Object.entries(REPORTS) as [ReportTarget, (typeof REPORTS)[ReportTarget]][]).map(([key, report]) => {
              const Icon = report.icon
              const isEmerald = report.accent === 'emerald'

              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => startGeneration(key)}
                  className={`group rounded-2xl border bg-slate-950/70 p-6 text-left backdrop-blur-md transition duration-200 hover:-translate-y-0.5 hover:bg-slate-900/80 focus-visible:outline-none focus-visible:ring-2 ${
                    isEmerald
                      ? 'border-emerald-400/20 hover:border-emerald-400/45 focus-visible:ring-emerald-400'
                      : 'border-violet-400/20 hover:border-violet-400/45 focus-visible:ring-violet-400'
                  }`}
                >
                  <div className={`mb-8 flex h-11 w-11 items-center justify-center rounded-xl border ${
                    isEmerald
                      ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                      : 'border-violet-400/20 bg-violet-400/10 text-violet-300'
                  }`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <h2 className="text-lg font-semibold">{report.title}</h2>
                  <p className="mt-2 min-h-12 text-sm leading-6 text-slate-400">{report.description}</p>
                  <span className={`mt-6 inline-flex items-center gap-2 text-sm font-medium ${
                    isEmerald ? 'text-emerald-300' : 'text-violet-300'
                  }`}>
                    Generate report
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  const tx         = TRANSACTIONS[txIdx]
  const particles  = makeParticles(txIdx, tx.income)
  const processed  = TRANSACTIONS.slice(0, litCount)
  const revenue    = processed.filter(t => t.income).reduce((s, t) => s + t.amount, 0)
  const expenses   = processed.filter(t => !t.income).reduce((s, t) => s + t.amount, 0)
  const categories = Array.from(new Set(processed.map(t => t.category)))
  const burstColor = tx.income ? '#34d399' : '#a78bfa'
  const scanning   = phase === 'scanning'
  const report     = REPORTS[reportTarget]
  const progress   = Math.round((litCount / TRANSACTIONS.length) * 100)

  return (
    <div className="relative flex h-full flex-col bg-[#03060f] text-white overflow-hidden">
      <style>{`
        @keyframes fade-in-up { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes count-up   { from{opacity:0;transform:scale(.93)} to{opacity:1;transform:scale(1)} }
        @keyframes pulse-soft { 0%,100%{opacity:1} 50%{opacity:.35} }
        .fade-in-up  { animation: fade-in-up .4s ease both; }
        .count-anim  { animation: count-up   .3s ease both; }
        .pulse-soft  { animation: pulse-soft 1.8s ease-in-out infinite; }
      `}</style>

      {/* ── Full-screen SVG canvas ── */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1000 580" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="bg-grd" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#0c1830"/>
            <stop offset="100%" stopColor="#03060f"/>
          </radialGradient>
          <radialGradient id="core-grd" cx="38%" cy="33%" r="65%">
            <stop offset="0%"   stopColor="#ede9fe"/>
            <stop offset="50%"  stopColor="#7c3aed"/>
            <stop offset="100%" stopColor="#2e1065"/>
          </radialGradient>
          <radialGradient id="halo-grd" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#5b21b6" stopOpacity="0.45"/>
            <stop offset="100%" stopColor="#5b21b6" stopOpacity="0"/>
          </radialGradient>
          <radialGradient id="radar-grd" cx="0%" cy="50%" r="100%">
            <stop offset="0%"   stopColor="#818cf8" stopOpacity="0.55"/>
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0"/>
          </radialGradient>

          {/* Holographic grid */}
          <pattern id="grid-pat" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#1a2e50" strokeWidth="0.5"/>
          </pattern>

          {/* Filters */}
          <filter id="orb-glow" x="-90%" y="-90%" width="280%" height="280%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="22" result="b1"/>
            <feGaussianBlur in="SourceGraphic" stdDeviation="9"  result="b2"/>
            <feMerge>
              <feMergeNode in="b1"/>
              <feMergeNode in="b2"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          <filter id="soft-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="pt-glow" x="-120%" y="-120%" width="340%" height="340%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        {/* Background */}
        <rect width="1000" height="580" fill="url(#bg-grd)"/>
        <rect width="1000" height="580" fill="url(#grid-pat)" opacity="0.35"/>

        {/* Star field */}
        {STARS.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="white" opacity={s.op}/>
        ))}

        {/* Orb ambient halo */}
        <circle cx={OX} cy={OY} r="230" fill="url(#halo-grd)" opacity="0.85"/>

        {/* ── Radar sweep (behind orb rings) ── */}
        <g filter="url(#soft-glow)">
          <path d={RADAR_PATH} fill="url(#radar-grd)" opacity="0.32">
            <animateTransform attributeName="transform" type="rotate"
              from={`0 ${OX} ${OY}`} to={`360 ${OX} ${OY}`} dur="5s" repeatCount="indefinite"/>
          </path>
        </g>

        {/* ── Rotating ray spokes ── */}
        <g opacity="0.13" filter="url(#soft-glow)">
          {RAYS.map((r, i) => (
            <line key={i} x1={r.x1} y1={r.y1} x2={r.x2} y2={r.y2} stroke="#c4b5fd" strokeWidth="0.9"/>
          ))}
          <animateTransform attributeName="transform" type="rotate"
            from={`0 ${OX} ${OY}`} to={`360 ${OX} ${OY}`} dur="24s" repeatCount="indefinite"/>
        </g>

        {/* ── Central orb (with glow filter) ── */}
        <g filter="url(#orb-glow)">
          {/* Outer pulsing coronas */}
          <circle cx={OX} cy={OY} r="150" fill="none" stroke="#5b21b6" strokeWidth="0.8" opacity="0.16">
            <animate attributeName="r"       values="140;165;140" dur="5s"   repeatCount="indefinite"/>
            <animate attributeName="opacity" values=".16;.06;.16"  dur="5s"   repeatCount="indefinite"/>
          </circle>
          <circle cx={OX} cy={OY} r="128" fill="none" stroke="#7c3aed" strokeWidth="0.7" opacity="0.1">
            <animate attributeName="r"       values="122;136;122" dur="3.5s" begin="1.2s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values=".1;.04;.1"    dur="3.5s" begin="1.2s" repeatCount="indefinite"/>
          </circle>

          {/* Outer dashed ring — slow CW */}
          <circle cx={OX} cy={OY} r="104" fill="none" stroke="#818cf8" strokeWidth="1.2" strokeDasharray="14 20" opacity="0.55">
            <animateTransform attributeName="transform" type="rotate"
              from={`0 ${OX} ${OY}`} to={`360 ${OX} ${OY}`} dur="16s" repeatCount="indefinite"/>
          </circle>

          {/* Tilted ellipse ring 1 — planetary ring effect */}
          <ellipse cx={OX} cy={OY} rx="128" ry="46"
            fill="none" stroke="#a78bfa" strokeWidth="0.9" strokeDasharray="9 18" opacity="0.32"
            transform={`rotate(22 ${OX} ${OY})`}/>

          {/* Tilted ellipse ring 2 — opposite tilt */}
          <ellipse cx={OX} cy={OY} rx="116" ry="40"
            fill="none" stroke="#34d399" strokeWidth="0.7" strokeDasharray="4 22" opacity="0.2"
            transform={`rotate(-38 ${OX} ${OY})`}/>

          {/* Inner dashed ring — faster CCW */}
          <circle cx={OX} cy={OY} r="78" fill="none" stroke="#34d399" strokeWidth="0.9" strokeDasharray="7 24" opacity="0.35">
            <animateTransform attributeName="transform" type="rotate"
              from={`0 ${OX} ${OY}`} to={`-360 ${OX} ${OY}`} dur="10s" repeatCount="indefinite"/>
          </circle>

          {/* Core sphere */}
          <circle cx={OX} cy={OY} r="47" fill="url(#core-grd)"/>

          {/* Pulsing inner glow */}
          <circle cx={OX} cy={OY} r="20" fill="#e0d9ff" opacity="0.3">
            <animate attributeName="r"       values="17;27;17" dur="3.2s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values=".3;.65;.3"  dur="3.2s" repeatCount="indefinite"/>
          </circle>

          {/* Specular highlight */}
          <ellipse cx={OX - 15} cy={OY - 16} rx="14" ry="9" fill="white" opacity="0.2"/>
        </g>

        {/* ── Ambient orbital dots ── */}
        {ORBITERS.map((o, i) => (
          <g key={i}>
            <animateTransform attributeName="transform" type="rotate"
              from={`${o.start} ${OX} ${OY}`} to={`${o.start + 360} ${OX} ${OY}`}
              dur={o.dur} repeatCount="indefinite"/>
            <circle cx={OX + o.r} cy={OY} r={o.size} fill={o.color} opacity={o.op} filter="url(#pt-glow)"/>
          </g>
        ))}

        {/* ── Inflow particles with trails ── */}
        {scanning && (
          <g key={`p-${txIdx}`} filter="url(#pt-glow)">
            {particles.map(p => (
              <g key={p.id}>
                {/* Trail 2 */}
                <circle r="1.5" fill={p.color} opacity="0">
                  <animateMotion path={p.path} dur={`${p.dur}s`} begin={`${(p.delay + 0.14).toFixed(2)}s`} fill="freeze"/>
                  <animate attributeName="opacity" values="0;.28;.28;0" keyTimes="0;0.12;0.82;1"
                    dur={`${p.dur}s`} begin={`${(p.delay + 0.14).toFixed(2)}s`} fill="freeze"/>
                </circle>
                {/* Trail 1 */}
                <circle r="2.5" fill={p.color} opacity="0">
                  <animateMotion path={p.path} dur={`${p.dur}s`} begin={`${(p.delay + 0.07).toFixed(2)}s`} fill="freeze"/>
                  <animate attributeName="opacity" values="0;.55;.55;0" keyTimes="0;0.12;0.82;1"
                    dur={`${p.dur}s`} begin={`${(p.delay + 0.07).toFixed(2)}s`} fill="freeze"/>
                </circle>
                {/* Main particle */}
                <circle r="3.5" fill={p.color} opacity="0">
                  <animateMotion path={p.path} dur={`${p.dur}s`} begin={`${p.delay.toFixed(2)}s`} fill="freeze"/>
                  <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.12;0.82;1"
                    dur={`${p.dur}s`} begin={`${p.delay.toFixed(2)}s`} fill="freeze"/>
                </circle>
              </g>
            ))}
          </g>
        )}

        {/* ── Absorption burst + core flash ── */}
        {phase === 'classified' && (
          <g key={`b-${txIdx}`}>
            {/* Bright core flash */}
            <circle cx={OX} cy={OY} r="47" fill="white" opacity="0">
              <animate attributeName="opacity" values="0;0.7;0" dur="0.4s"  fill="remove"/>
              <animate attributeName="r"       values="47;60;47"  dur="0.4s"  fill="remove"/>
            </circle>
            {/* First burst ring */}
            <circle cx={OX} cy={OY} r="47" fill="none" stroke={burstColor} strokeWidth="3" opacity="0">
              <animate attributeName="r"       values="47;175" dur="0.95s" fill="remove"/>
              <animate attributeName="opacity" values="0.9;0"  dur="0.95s" fill="remove"/>
            </circle>
            {/* Second burst ring */}
            <circle cx={OX} cy={OY} r="47" fill="none" stroke={burstColor} strokeWidth="1.5" opacity="0">
              <animate attributeName="r"       values="47;245" dur="1.05s" begin="0.08s" fill="remove"/>
              <animate attributeName="opacity" values="0.55;0" dur="1.05s" begin="0.08s" fill="remove"/>
            </circle>
          </g>
        )}
      </svg>

      {/* ── Header overlay ── */}
      <div className="relative z-10 flex items-center gap-3 border-b border-white/5 bg-black/40 px-8 py-4 backdrop-blur-md">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75 animate-ping"/>
          <span className="relative h-2 w-2 rounded-full bg-violet-400"/>
        </span>
        <span className="text-sm font-semibold">AI Insights</span>
        <span className="text-slate-600">—</span>
        {phase === 'done' ? (
          <span className="text-sm text-emerald-400">{report.title} ready — opening report…</span>
        ) : scanning ? (
          <span className="pulse-soft text-sm text-slate-400">
            Generating {report.title}: <span className="text-white">{tx.contact}</span>
          </span>
        ) : (
          <span className="text-sm text-slate-400">
            Classified: <span className="text-violet-300">{tx.category}</span>
          </span>
        )}
        <span className="ml-auto text-xs text-slate-600">{litCount} / {TRANSACTIONS.length}</span>
      </div>

      {/* ── Content panels ── */}
      <div className="relative z-10 flex flex-1 items-center justify-between px-10 py-8">

        {/* Left — current transaction */}
        <div className={`w-52 rounded-2xl border p-5 backdrop-blur-md transition-colors duration-500 ${
          scanning ? 'border-amber-400/35 bg-black/55' : 'border-violet-500/35 bg-black/55'
        }`}>
          <p className="mb-3 text-[10px] font-medium uppercase tracking-widest text-slate-500">Reading</p>
          <p className="truncate text-sm text-slate-400">{tx.contact}</p>
          <p key={`amt-${txIdx}`} className={`count-anim mt-1 text-2xl font-bold ${tx.income ? 'text-emerald-400' : 'text-indigo-400'}`}>
            {tx.income ? '+' : '−'}{fmt(tx.amount)}
          </p>
          <div className="mt-3 min-h-[24px]">
            {scanning ? (
              <span className="pulse-soft flex items-center gap-1.5 text-xs text-amber-400/80">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400"/>
                Identifying…
              </span>
            ) : (
              <span key={`cat-${txIdx}`} className="fade-in-up inline-flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-0.5 text-[11px] text-violet-300">
                ✓ {tx.category}
              </span>
            )}
          </div>
        </div>

        <div className="flex-1"/>

        {/* Right — live summary */}
        <div className="w-52 rounded-2xl border border-white/10 bg-black/55 p-5 backdrop-blur-md">
          <p className="mb-4 text-[10px] font-medium uppercase tracking-widest text-slate-500">Insights</p>

          <div className="mb-4">
            <p className="mb-0.5 text-xs text-slate-600">Revenue</p>
            <p key={revenue} className="count-anim text-2xl font-bold text-emerald-400">
              {revenue > 0 ? fmt(revenue) : '—'}
            </p>
          </div>

          <div className="mb-4">
            <p className="mb-0.5 text-xs text-slate-600">Expenses</p>
            <p key={expenses} className="count-anim text-2xl font-bold text-indigo-400">
              {expenses > 0 ? fmt(expenses) : '—'}
            </p>
          </div>

          <div>
            <p className="mb-2 text-xs text-slate-600">Categories found</p>
            <div className="flex flex-wrap gap-1">
              {categories.map(c => (
                <span key={c} className="fade-in-up rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300">
                  {c}
                </span>
              ))}
              {categories.length === 0 && <span className="text-xs text-slate-700">Waiting…</span>}
            </div>
          </div>

          {litCount > 0 && (
            <div className="fade-in-up mt-4 rounded-xl border border-violet-500/20 bg-violet-500/5 px-3 py-2.5">
              <p className="text-[10px] text-violet-400/70">AI confidence</p>
              <p className="mt-0.5 text-xl font-bold text-violet-300">94.2%</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Progress footer ── */}
      <div className="relative z-10 border-t border-white/5 bg-black/40 px-8 py-3 backdrop-blur-md">
        <div className="mb-1.5 flex justify-between text-xs text-slate-600">
          <span>Generating {report.title} · 2 records per second</span>
          <span>{progress}%</span>
        </div>
        <div className="h-px overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full bg-violet-500 transition-[width] duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  )
}
