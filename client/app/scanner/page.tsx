"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
import { RefreshCw, ExternalLink, ChevronDown, ChevronUp, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  PageLayout,
  DashboardRightPanel,
  PageHeader
} from "@/components"
import { useDashboardQueries } from "@/hooks/useDashboardQueries"
import { NAMES } from "@/constants"
import { AGENT_IDS as DEFAULT_AGENT_IDS } from "@/lib/api"

// Types
interface Ticker {
  symbol: string
  price: number
  change24: number
  change7d?: number
  change1h?: number
  change4h?: number
  quoteVolume: number
  high24: number
  low24: number
  funding: number | null
  volRatio?: number
  oiChange24?: number
  dailyCloses?: number[]
  hourlyCloses?: number[]
}

interface Signal {
  score: number
  note?: string
}

interface Candidate extends Ticker {
  score: number
  signals: Record<string, Signal>
  strongCount: number
  pumpFlagged: boolean
  narrativeMult: number
  sector: string
}

interface SectorData {
  tokens: string[]
  sum24: number
  sum7d: number
  count: number
  avg24: number
  avg7d: number
  momentum: number
}

// Constants
const CONFIG = {
  API_BASE: "https://fapi.binance.com",
  TOP_N_DISPLAY: 40,
  PHASE1_TOP_N: 70,
  MAX_SYMBOLS: 400,
  AUTO_REFRESH_MS: 120000,
  BATCH_SIZE: 12,
  BATCH_DELAY_MS: 250,
  MIN_QUOTE_VOLUME: 5_000_000,
  BTC_SYMBOL: "BTCUSDT",
  ETH_SYMBOL: "ETHUSDT",
}

const SECTORS: Record<string, string> = {
  BTCUSDT: "L1", ETHUSDT: "L1", SOLUSDT: "L1", AVAXUSDT: "L1",
  BNBUSDT: "L1", ADAUSDT: "L1", NEARUSDT: "L1", APTUSDT: "L1",
  SUIUSDT: "L1", TIAUSDT: "L1", SEIUSDT: "L1", INJUSDT: "L1",
  ATOMUSDT: "L1", DOTUSDT: "L1", TRXUSDT: "L1", XRPUSDT: "L1",
  TONUSDT: "L1", FTMUSDT: "L1", KASUSDT: "L1", ICPUSDT: "L1",
  ARBUSDT: "L2", OPUSDT: "L2", MATICUSDT: "L2", STRKUSDT: "L2",
  IMXUSDT: "L2", METISUSDT: "L2", MANTAUSDT: "L2", BLASTUSDT: "L2",
  FETUSDT: "AI", AGIXUSDT: "AI", RENDERUSDT: "AI", RNDRUSDT: "AI",
  WLDUSDT: "AI", TAOUSDT: "AI", OCEANUSDT: "AI", ARKMUSDT: "AI",
  DOGEUSDT: "MEME", SHIBUSDT: "MEME", PEPEUSDT: "MEME", WIFUSDT: "MEME",
  BONKUSDT: "MEME", FLOKIUSDT: "MEME", MEMEUSDT: "MEME", BOMEUSDT: "MEME",
  UNIUSDT: "DEFI", AAVEUSDT: "DEFI", MKRUSDT: "DEFI", CRVUSDT: "DEFI",
  COMPUSDT: "DEFI", SUSHIUSDT: "DEFI", SNXUSDT: "DEFI", LDOUSDT: "DEFI",
  PENDLEUSDT: "DEFI", GMXUSDT: "DEFI", JUPUSDT: "DEFI", ENAUSDT: "DEFI",
  ONDOUSDT: "RWA", POLYXUSDT: "RWA", RSRUSDT: "RWA",
  GALAUSDT: "GAME", APEUSDT: "GAME", AXSUSDT: "GAME", SANDUSDT: "GAME",
  MANAUSDT: "GAME", ILVUSDT: "GAME", GMTUSDT: "GAME", MAGICUSDT: "GAME",
  HNTUSDT: "DEPIN", AKTUSDT: "DEPIN", FILUSDT: "DEPIN", ARUSDT: "DEPIN",
  LINKUSDT: "INFRA", GRTUSDT: "INFRA", QNTUSDT: "INFRA", RUNEUSDT: "INFRA",
}

const MODE_WEIGHTS: Record<string, Record<string, number>> = {
  momentum: { momentum: 1.5, volume: 1.3, breakout: 1.0, compression: 0.5, funding: 0.7, oi: 0.9, capitulation: 0.3, early: 1.2 },
  breakout: { momentum: 0.9, volume: 1.2, breakout: 1.5, compression: 1.3, funding: 0.7, oi: 1.0, capitulation: 0.5, early: 1.0 },
  reversal: { momentum: 0.3, volume: 1.0, breakout: 0.5, compression: 0.7, funding: 1.4, oi: 1.2, capitulation: 1.5, early: 0.4 },
  compression: { momentum: 0.5, volume: 0.8, breakout: 1.0, compression: 1.7, funding: 0.8, oi: 1.0, capitulation: 0.4, early: 0.9 },
}

const SIGNAL_META: { key: string; emoji: string; name: string; color: string }[] = [
  { key: "momentum", emoji: "🚀", name: "모멘텀", color: "var(--chip-momentum)" },
  { key: "volume", emoji: "🔥", name: "거래량", color: "var(--chip-volume)" },
  { key: "breakout", emoji: "💎", name: "브레이크아웃", color: "var(--chip-breakout)" },
  { key: "compression", emoji: "🎯", name: "압축", color: "var(--chip-compression)" },
  { key: "funding", emoji: "⚡", name: "펀딩", color: "var(--chip-funding)" },
  { key: "oi", emoji: "🧲", name: "OI", color: "var(--chip-oi)" },
  { key: "capitulation", emoji: "💀", name: "청산", color: "var(--chip-capitulation)" },
  { key: "early", emoji: "🌊", name: "조기", color: "var(--chip-early)" },
]

// Utilities
const getSector = (sym: string) => SECTORS[sym] || "—"

const fmt = {
  price: (v: number | null | undefined) => {
    if (v == null) return "—"
    const n = Number(v)
    if (n >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 2 })
    if (n >= 1) return n.toFixed(3)
    if (n >= 0.01) return n.toFixed(4)
    if (n >= 0.0001) return n.toFixed(6)
    return n.toExponential(2)
  },
  pct: (v: number | null | undefined, decimals = 2) => {
    if (v == null || isNaN(v)) return "—"
    const n = Number(v)
    const s = n.toFixed(decimals)
    return (n >= 0 ? "+" : "") + s + "%"
  },
  multiplier: (v: number | null | undefined, decimals = 1) => {
    if (v == null || isNaN(v)) return "—"
    return Number(v).toFixed(decimals) + "x"
  },
  time: (date: Date) => {
    const pad = (n: number) => String(n).padStart(2, "0")
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  },
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function fetchJson(url: string, retries = 2): Promise<unknown> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const r = await fetch(url)
      if (r.status === 429) {
        await sleep(1000 * (attempt + 1))
        continue
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return await r.json()
    } catch (e) {
      if (attempt === retries) throw e
      await sleep(300 * (attempt + 1))
    }
  }
  return null
}

// Technical Indicators
function calcRSI(closes: number[], period = 14): number {
  if (closes.length <= period) return 50
  let gains = 0, losses = 0
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1]
    if (diff > 0) gains += diff
    else losses -= diff
  }
  let avgGain = gains / period, avgLoss = losses / period
  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1]
    if (diff > 0) {
      avgGain = (avgGain * (period - 1) + diff) / period
      avgLoss = (avgLoss * (period - 1)) / period
    } else {
      avgGain = (avgGain * (period - 1)) / period
      avgLoss = (avgLoss * (period - 1) + (-diff)) / period
    }
  }
  if (avgLoss === 0) return 100
  const rs = avgGain / avgLoss
  return 100 - (100 / (1 + rs))
}

function calcBBWidth(closes: number[], period = 20, mult = 2): number | null {
  if (closes.length < period) return null
  const recent = closes.slice(-period)
  const mean = recent.reduce((a, b) => a + b, 0) / period
  const variance = recent.reduce((a, b) => a + (b - mean) ** 2, 0) / period
  const stddev = Math.sqrt(variance)
  return ((mean + mult * stddev) - (mean - mult * stddev)) / mean
}

// Signal Calculators
function sigMomentum(token: Ticker, btc: Ticker): Signal {
  const rs24 = token.change24 - btc.change24
  const rs7d = (token.change7d || 0) - (btc.change7d || 0)
  let s = 0
  s += Math.max(0, Math.min(50, rs24 * 5))
  s += Math.max(0, Math.min(40, rs7d * 2))
  if (token.change24 < -2) s *= 0.3
  return { score: Math.max(0, Math.min(100, s)), note: `RS24:${rs24.toFixed(1)} RS7:${rs7d.toFixed(1)}` }
}

function sigVolume(token: Ticker): Signal {
  if (!token.volRatio || token.volRatio < 1) return { score: 0 }
  const s = Math.min(100, Math.log2(token.volRatio) * 35)
  return { score: Math.max(0, s), note: `${token.volRatio.toFixed(2)}x` }
}

function sigBreakout(token: Ticker): Signal {
  if (!token.dailyCloses || token.dailyCloses.length < 15) return { score: 0 }
  const high30 = Math.max(...token.dailyCloses.slice(-30))
  const distance = (high30 - token.price) / high30
  if (distance > 0.15) return { score: 0, note: `far (${(distance * 100).toFixed(1)}% below)` }
  let s = Math.max(0, 60 - distance * 400)
  if (token.volRatio && token.volRatio > 1.3) s += Math.min(40, (token.volRatio - 1) * 30)
  return { score: Math.max(0, Math.min(100, s)), note: `${(distance * 100).toFixed(1)}% below 30d high` }
}

function sigCompression(token: Ticker): Signal {
  if (!token.hourlyCloses || token.hourlyCloses.length < 40) return { score: 0 }
  const widths: number[] = []
  for (let i = 20; i < token.hourlyCloses.length; i++) {
    const w = calcBBWidth(token.hourlyCloses.slice(0, i + 1), 20)
    if (w != null) widths.push(w)
  }
  if (widths.length < 10) return { score: 0 }
  const current = widths[widths.length - 1]
  const sorted = [...widths].sort((a, b) => a - b)
  const rank = sorted.indexOf(current)
  const pct = rank / (sorted.length - 1)
  let s = Math.max(0, 100 - pct * 250)
  const recent = token.hourlyCloses.slice(-24)
  const rHigh = Math.max(...recent)
  const rLow = Math.min(...recent)
  const rangePct = (rHigh - rLow) / ((rHigh + rLow) / 2)
  const isTrending = Math.abs(token.change24 || 0) > 4
  if (isTrending) s *= 0.3
  if (rangePct > 0.10) s *= 0.6
  return { score: s, note: `BB ${(pct * 100).toFixed(0)}%ile · 범위 ${(rangePct * 100).toFixed(1)}%` }
}

function sigFunding(token: Ticker): Signal {
  if (token.funding == null) return { score: 0 }
  const abs = Math.abs(token.funding)
  const s = Math.min(100, abs * 70000)
  const dir = token.funding > 0 ? "롱 과열" : "숏 과열"
  return { score: s, note: `${(token.funding * 100).toFixed(4)}% ${dir}` }
}

function sigOI(token: Ticker): Signal {
  if (token.oiChange24 == null) return { score: 0 }
  const price24 = token.change24
  const oi24 = token.oiChange24
  let s = 0
  let note = ""
  const bigOI = oi24 > 15
  const flatPrice = Math.abs(price24) < 3
  if (bigOI && flatPrice) { s = 75; note = `OI +${oi24.toFixed(1)}% (축적)` }
  else if (oi24 > 20 && price24 < -2) { s = 70; note = `OI +${oi24.toFixed(1)}% 숏 빌드업` }
  else if (oi24 > 10 && price24 > 3) { s = 35; note = `OI +${oi24.toFixed(1)}% 트렌드 확정` }
  else if (oi24 < -10 && price24 > 3) { s = 40; note = `OI ${oi24.toFixed(1)}% 약한 랠리` }
  else if (Math.abs(oi24) > 8) { s = Math.min(60, Math.abs(oi24) * 3); note = `OI ${oi24 > 0 ? "+" : ""}${oi24.toFixed(1)}%` }
  return { score: Math.max(0, Math.min(100, s)), note }
}

function sigCapitulation(token: Ticker): Signal {
  if (!token.hourlyCloses || token.hourlyCloses.length < 24) return { score: 0 }
  const rsi = calcRSI(token.hourlyCloses, 14)
  let biggestDrop = 0
  for (let i = 1; i < token.hourlyCloses.length; i++) {
    const d = (token.hourlyCloses[i] - token.hourlyCloses[i - 1]) / token.hourlyCloses[i - 1]
    if (d < biggestDrop) biggestDrop = d
  }
  const recent = token.hourlyCloses.slice(-6)
  const recentLow = Math.min(...recent)
  const bounceFromLow = (token.price - recentLow) / recentLow
  let s = 0
  if (rsi < 35 && biggestDrop < -0.05) {
    s = 40
    s += Math.min(30, (35 - rsi) * 2)
    if (bounceFromLow > 0 && bounceFromLow < 0.04) s += 20
    if (token.funding != null && token.funding < -0.0002) s += 10
  }
  return { score: Math.max(0, Math.min(100, s)), note: `RSI ${rsi.toFixed(0)}, 최대낙폭 ${(biggestDrop * 100).toFixed(1)}%` }
}

function sigEarly(token: Ticker): Signal {
  if (!token.change1h || token.change24 == null) return { score: 0 }
  const h1 = token.change1h
  const h4 = token.change4h || 0
  const h24 = token.change24
  let s = 0
  if (h1 > 1.5 && h24 < 6) s += Math.min(40, h1 * 15)
  if (h4 > 1 && h4 < 10) s += Math.min(30, h4 * 6)
  if (token.volRatio && token.volRatio > 1.3) s += 20
  if (h24 > 15) s *= 0.2
  return { score: Math.max(0, Math.min(100, s)), note: `1h ${h1.toFixed(1)}% / 4h ${h4.toFixed(1)}%` }
}

// Main Component
export default function SoloScanner() {
  const [mode, setMode] = useState<string>("momentum")
  const [minScore, setMinScore] = useState<number>(0)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [btcData, setBtcData] = useState<Ticker | null>(null)
  const [ethData, setEthData] = useState<Ticker | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [expandedSym, setExpandedSym] = useState<string | null>(null)
  const [regimeAdaptive, setRegimeAdaptive] = useState(true)
  const [regimeLabel, setRegimeLabel] = useState("MIXED")
  const [regimeNote, setRegimeNote] = useState("")
  const [sectorMomentum, setSectorMomentum] = useState<{ ranked: [string, SectorData][] } | null>(null)
  const [topSectors, setTopSectors] = useState<Set<string>>(new Set())
  const [botSectors, setBotSectors] = useState<Set<string>>(new Set())
  const [loadProgress, setLoadProgress] = useState("")
  const [avgFunding, setAvgFunding] = useState<number>(0)
  const [breadth, setBreadth] = useState({ up: 0, down: 0, pct: 50 })
  const [clock, setClock] = useState<Date | null>(null)
  const [mounted, setMounted] = useState(false)

  // Dashboard queries for the right panel
  const {
    evolutionEvents,
    decisionLogs,
    botTrades,
    bots,
    automationStatus,
    metricsData,
    dashboardProgress,
    toggleAutomation
  } = useDashboardQueries({
    enableEvolutionLogs: true,
    enableDecisionLogs: true,
    statsIntervalMs: 6000,
    logsIntervalMs: 8000,
  });

  const runtimeAgentIds = useMemo(() => {
    if (bots && bots.length > 0) return bots.map((b: any) => b.id).sort();
    return [...DEFAULT_AGENT_IDS].sort();
  }, [bots]);

  const agentNames = useMemo(() => {
    return runtimeAgentIds.map((id, idx) => {
      const bot = bots.find((b: any) => b.id === id);
      if (bot) return bot.name;
      return NAMES[idx] || "Agent " + (idx + 1);
    });
  }, [bots, runtimeAgentIds]);

  // Clock update
  useEffect(() => {
    setMounted(true)
    setClock(new Date())
    const interval = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  const adaptiveWeights = useCallback((modeKey: string, regime: string) => {
    const base = { ...MODE_WEIGHTS[modeKey] }
    if (!regimeAdaptive) return base
    if (regime === "RISK-OFF" || regime === "WEAK") {
      base.momentum *= 0.55
      base.breakout *= 0.6
      base.early *= 0.5
      base.capitulation *= 1.6
      base.funding *= 1.35
      base.oi *= 1.15
      base.compression *= 1.2
    } else if (regime === "RISK-ON") {
      base.momentum *= 1.25
      base.breakout *= 1.2
      base.early *= 1.35
      base.volume *= 1.15
      base.capitulation *= 0.4
    } else if (regime === "BROAD") {
      base.momentum *= 1.1
      base.breakout *= 1.1
    }
    return base
  }, [regimeAdaptive])

  const computeComposite = useCallback((token: Ticker, btc: Ticker, modeKey: string, regime: string, topSecs: Set<string>, botSecs: Set<string>) => {
    const signals: Record<string, Signal> = {
      momentum: sigMomentum(token, btc),
      volume: sigVolume(token),
      breakout: sigBreakout(token),
      compression: sigCompression(token),
      funding: sigFunding(token),
      oi: sigOI(token),
      capitulation: sigCapitulation(token),
      early: sigEarly(token),
    }

    let pumpFlagged = false
    if (token.change24 > 25) {
      signals.momentum.score *= 0.25
      signals.breakout.score *= 0.25
      signals.early.score *= 0.10
      pumpFlagged = true
    } else if (token.change24 < -25) {
      signals.capitulation.score = Math.min(100, signals.capitulation.score * 1.3)
    }

    const weights = adaptiveWeights(modeKey, regime)
    let weightedSum = 0, totalWeight = 0
    for (const k in signals) {
      weightedSum += signals[k].score * weights[k]
      totalWeight += weights[k] * 100
    }
    let composite = (weightedSum / totalWeight) * 100

    const strong = Object.values(signals).filter(s => s.score > 50).length
    if (strong >= 4) composite *= 1.30
    else if (strong >= 3) composite *= 1.20
    else if (strong >= 2) composite *= 1.10

    if (signals.momentum.score > 60 && signals.capitulation.score > 60) composite *= 0.7

    const sector = getSector(token.symbol)
    let narrativeMult = 1.0
    if (sector !== "—") {
      if (topSecs.has(sector)) narrativeMult = 1.15
      else if (botSecs.has(sector)) narrativeMult = 0.90
    }
    composite *= narrativeMult

    return {
      score: Math.max(0, Math.min(100, composite)),
      signals,
      strongCount: strong,
      pumpFlagged,
      narrativeMult,
      sector,
    }
  }, [adaptiveWeights])

  const runPipeline = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      setLoadProgress("시세 정보 및 펀딩율 수집 중…")
      const [tickersRaw, fundingArr] = await Promise.all([
        fetchJson(`${CONFIG.API_BASE}/fapi/v1/ticker/24hr`) as Promise<Array<{
          symbol: string
          lastPrice: string
          priceChangePercent: string
          quoteVolume: string
          highPrice: string
          lowPrice: string
        }>>,
        fetchJson(`${CONFIG.API_BASE}/fapi/v1/premiumIndex`) as Promise<Array<{
          symbol: string
          lastFundingRate: string
        }>>,
      ])

      const fundingMap: Record<string, number> = {}
      fundingArr.forEach(f => { fundingMap[f.symbol] = parseFloat(f.lastFundingRate) })

      const filtered = tickersRaw
        .filter(t => t.symbol.endsWith("USDT"))
        .filter(t => !t.symbol.includes("_"))
        .filter(t => !/^(USDC|BUSD|FDUSD|DAI|TUSD|USDP)USDT$/.test(t.symbol))
        .filter(t => parseFloat(t.quoteVolume) >= CONFIG.MIN_QUOTE_VOLUME)
        .map(t => ({
          symbol: t.symbol,
          price: parseFloat(t.lastPrice),
          change24: parseFloat(t.priceChangePercent),
          quoteVolume: parseFloat(t.quoteVolume),
          high24: parseFloat(t.highPrice),
          low24: parseFloat(t.lowPrice),
          funding: fundingMap[t.symbol] ?? null,
        }))
        .sort((a, b) => b.quoteVolume - a.quoteVolume)
        .slice(0, CONFIG.MAX_SYMBOLS)

      const btc = filtered.find(t => t.symbol === CONFIG.BTC_SYMBOL)
      const eth = filtered.find(t => t.symbol === CONFIG.ETH_SYMBOL)
      if (!btc) throw new Error("BTC 데이터 없음")
      setBtcData(btc as Ticker)
      setEthData(eth as Ticker || null)

      // Calculate breadth and funding
      const up = filtered.filter(t => t.change24 > 0).length
      const down = filtered.filter(t => t.change24 < 0).length
      const total = up + down
      const upPct = total > 0 ? up / total * 100 : 50
      setBreadth({ up, down, pct: upPct })

      let totalVol = 0, weighted = 0
      fundingArr.forEach(f => {
        const t = filtered.find(x => x.symbol === f.symbol)
        if (!t) return
        totalVol += t.quoteVolume
        weighted += parseFloat(f.lastFundingRate) * t.quoteVolume
      })
      const avgF = totalVol > 0 ? weighted / totalVol : 0
      setAvgFunding(avgF)

      // Regime
      let regime, note
      if (btc.change24 > 3 && upPct > 60) { regime = "RISK-ON"; note = "광범위 상승, 알트 추세 유리" }
      else if (btc.change24 < -3 && upPct < 40) { regime = "RISK-OFF"; note = "하락 체제, 숏 또는 관망" }
      else if (upPct > 55) { regime = "BROAD"; note = "섹터 로테이션 중" }
      else if (upPct < 45) { regime = "WEAK"; note = "약세 편향, 신중" }
      else { regime = "MIXED"; note = "혼조세, 개별 종목 선택적" }
      setRegimeLabel(regime)
      setRegimeNote(note)

      setLoadProgress(`Phase 1: ${filtered.length}종목 기본 분석…`)

      // Pre-score
      filtered.forEach(t => {
        (t as Ticker & { _prescore: number })._prescore = (t.change24 - btc.change24) + Math.log10(Math.max(1, t.quoteVolume / 10_000_000))
      })

      const sortedByScore = [...filtered].sort((a, b) =>
        ((b as Ticker & { _prescore: number })._prescore || 0) - ((a as Ticker & { _prescore: number })._prescore || 0)
      ).slice(0, CONFIG.PHASE1_TOP_N)
      const extremeFunding = filtered.filter(t => Math.abs(t.funding || 0) > 0.0003)
      const bigLosers = [...filtered].sort((a, b) => a.change24 - b.change24).slice(0, 15)
      const phase2Set = new Map<string, Ticker>()
        ;[...sortedByScore, ...extremeFunding, ...bigLosers].forEach(t => phase2Set.set(t.symbol, t as Ticker))
      phase2Set.set(btc.symbol, btc as Ticker)
      if (eth) phase2Set.set(eth.symbol, eth as Ticker)
      const phase2 = [...phase2Set.values()]

      setLoadProgress(`Phase 2: ${phase2.length}종목 심층 분석…`)

      // Batch fetch klines and OI
      for (let i = 0; i < phase2.length; i += CONFIG.BATCH_SIZE) {
        const slice = phase2.slice(i, i + CONFIG.BATCH_SIZE)
        await Promise.all(slice.map(async (t) => {
          try {
            const [dailyRaw, h1Close, oiHist] = await Promise.all([
              fetchJson(`${CONFIG.API_BASE}/fapi/v1/klines?symbol=${t.symbol}&interval=1d&limit=30`).catch(() => null) as Promise<number[][] | null>,
              fetchJson(`${CONFIG.API_BASE}/fapi/v1/klines?symbol=${t.symbol}&interval=1h&limit=60`).then((k: unknown) => (k as number[][]).map(c => parseFloat(String(c[4])))).catch(() => null) as Promise<number[] | null>,
              fetchJson(`${CONFIG.API_BASE}/futures/data/openInterestHist?symbol=${t.symbol}&period=1h&limit=24`).then((o: unknown) => (o as Array<{ sumOpenInterest: string }>).map(x => parseFloat(x.sumOpenInterest))).catch(() => null) as Promise<number[] | null>,
            ])
            if (dailyRaw) {
              t.dailyCloses = dailyRaw.map(c => parseFloat(String(c[4])))
              const quoteVols = dailyRaw.map(c => parseFloat(String(c[7])))
              if (quoteVols.length >= 4) {
                const today = quoteVols[quoteVols.length - 1]
                const prev = quoteVols.slice(-8, -1)
                const avg = prev.length ? prev.reduce((a, b) => a + b, 0) / prev.length : 0
                t.volRatio = avg > 0 ? today / avg : 1
              }
              if (t.dailyCloses.length >= 8) {
                const lastPrice = t.dailyCloses[t.dailyCloses.length - 1]
                const price7d = t.dailyCloses[t.dailyCloses.length - 8]
                t.change7d = (lastPrice - price7d) / price7d * 100
              }
            }
            t.hourlyCloses = h1Close || undefined
            if (h1Close && h1Close.length >= 5) {
              t.change1h = (h1Close[h1Close.length - 1] - h1Close[h1Close.length - 2]) / h1Close[h1Close.length - 2] * 100
              t.change4h = (h1Close[h1Close.length - 1] - h1Close[h1Close.length - 5]) / h1Close[h1Close.length - 5] * 100
            }
            if (oiHist && oiHist.length >= 20) {
              t.oiChange24 = (oiHist[oiHist.length - 1] - oiHist[0]) / oiHist[0] * 100
            }
          } catch {
            // skip
          }
        }))
        setLoadProgress(`Phase 2: ${Math.min(i + CONFIG.BATCH_SIZE, phase2.length)}/${phase2.length} 종목 분석 중…`)
        if (i + CONFIG.BATCH_SIZE < phase2.length) await sleep(CONFIG.BATCH_DELAY_MS)
      }

      const btc2 = phase2.find(t => t.symbol === CONFIG.BTC_SYMBOL)
      const eth2 = phase2.find(t => t.symbol === CONFIG.ETH_SYMBOL)
      if (btc2) setBtcData(btc2)
      if (eth2) setEthData(eth2)

      // Sector momentum
      const bySector: Record<string, SectorData> = {}
      phase2.forEach(t => {
        const s = getSector(t.symbol)
        if (s === "—") return
        if (!bySector[s]) bySector[s] = { tokens: [], sum24: 0, sum7d: 0, count: 0, avg24: 0, avg7d: 0, momentum: 0 }
        bySector[s].tokens.push(t.symbol)
        bySector[s].sum24 += (t.change24 || 0)
        bySector[s].sum7d += (t.change7d || 0)
        bySector[s].count++
      })
      for (const s in bySector) {
        const v = bySector[s]
        v.avg24 = v.sum24 / v.count
        v.avg7d = v.sum7d / v.count
        v.momentum = v.avg24 + v.avg7d * 0.4
      }
      const ranked = Object.entries(bySector)
        .filter(([, v]) => v.count >= 2)
        .sort((a, b) => b[1].momentum - a[1].momentum) as [string, SectorData][]
      setSectorMomentum({ ranked })

      const newTopSectors = new Set(ranked.slice(0, 3).map(([name]) => name))
      const newBotSectors = new Set(ranked.slice(-2).map(([name]) => name))
      setTopSectors(newTopSectors)
      setBotSectors(newBotSectors)

      setLoadProgress("스코어 계산 중…")

      const scored = phase2
        .filter(t => t.symbol !== CONFIG.BTC_SYMBOL && t.symbol !== CONFIG.ETH_SYMBOL)
        .map(t => {
          const { score, signals, strongCount, pumpFlagged, narrativeMult, sector } = computeComposite(t, btc2 || btc as Ticker, mode, regime, newTopSectors, newBotSectors)
          return { ...t, score, signals, strongCount, pumpFlagged, narrativeMult, sector } as Candidate
        })
        .sort((a, b) => b.score - a.score)

      setCandidates(scored)
      setLastUpdate(new Date())
    } catch (e) {
      setError(`스캔 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`)
    } finally {
      setLoading(false)
    }
  }, [mode, computeComposite])

  useEffect(() => {
    runPipeline()
    const interval = setInterval(runPipeline, CONFIG.AUTO_REFRESH_MS)
    return () => clearInterval(interval)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Rescore when mode changes
  useEffect(() => {
    if (!btcData || candidates.length === 0) return
    const rescored = candidates
      .map(t => {
        const { score, signals, strongCount, pumpFlagged, narrativeMult, sector } = computeComposite(t, btcData, mode, regimeLabel, topSectors, botSectors)
        return { ...t, score, signals, strongCount, pumpFlagged, narrativeMult, sector }
      })
      .sort((a, b) => b.score - a.score)
    setCandidates(rescored)
  }, [mode, regimeAdaptive]) // eslint-disable-line react-hooks/exhaustive-deps

  const displayCandidates = useMemo(() =>
    candidates.filter(c => c.score >= minScore).slice(0, CONFIG.TOP_N_DISPLAY),
    [candidates, minScore]
  )

  return (
    <PageLayout rightWidth="lg:w-[420px]">
      <PageLayout.Side>
        <DashboardRightPanel
          agentIds={runtimeAgentIds}
          names={agentNames}
          metricsData={metricsData ?? undefined}
          progress={dashboardProgress ?? undefined}
          evolutionEvents={evolutionEvents}
          decisionLogs={decisionLogs}
          botTrades={botTrades}
          automationStatus={automationStatus}
          onToggleAutomation={toggleAutomation}
          scannerContent={
            <div className="flex flex-col gap-8 p-6 pb-20">
              {/* Regime Stats */}
              <div className="flex flex-col gap-3">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-[#bd93f9]" />
                  Market Regime
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <SideStat label="BTC" value={`$${fmt.price(btcData?.price)}`} note={fmt.pct(btcData?.change24)} noteColor={btcData && btcData.change24 > 0 ? "text-green-400" : "text-red-400"} />
                  <SideStat label="ETH" value={`$${fmt.price(ethData?.price)}`} note={fmt.pct(ethData?.change24)} noteColor={ethData && ethData.change24 > 0 ? "text-green-400" : "text-red-400"} />
                  <SideStat label="AVG FUND" value={`${(avgFunding * 100).toFixed(4)}%`} note={avgFunding > 0.0002 ? "숏 전환" : avgFunding < -0.0001 ? "롱 전환" : "중립"} />
                  <SideStat label="BREADTH" value={`${breadth.up}/${breadth.down}`} note={`상승 ${breadth.pct.toFixed(0)}%`} />
                </div>
                <div className="bg-white/5 border border-white/10 rounded-lg px-3 py-3 mt-1 backdrop-blur-md">
                  <div className="font-mono text-[8px] tracking-[0.3em] text-slate-500 uppercase mb-0.5">시장 체제</div>
                  <div className={cn("font-mono text-lg font-black mb-0.5 tracking-tight", 
                    regimeLabel === "RISK-ON" && "text-green-400",
                    regimeLabel === "RISK-OFF" && "text-red-400",
                    regimeLabel === "WEAK" && "text-amber-400"
                  )}>{regimeLabel}</div>
                  <div className="text-[10px] text-slate-400 leading-tight">
                    {regimeNote} {regimeAdaptive && regimeLabel !== "MIXED" && "· ADAPTIVE ON"}
                  </div>
                </div>
              </div>

              {/* Sector Rotation */}
              <div className="flex flex-col gap-3">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-[#8b5cf6]" />
                  Sector Rotation
                </h3>
                <div className="flex flex-row flex-wrap gap-1.5">
                  {sectorMomentum?.ranked.map(([name, v], i) => (
                    <div key={name} className="flex-1 min-w-[100px] flex flex-col gap-1 p-2.5 bg-white/5 border border-white/10 rounded-md hover:bg-white/[0.08] transition-colors">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[8px] font-bold tracking-wider text-slate-500 uppercase">{name}</span>
                        <span className="text-[8px] text-slate-600 font-bold">{v.count}</span>
                      </div>
                      <div className="flex items-baseline justify-between">
                        <span className={cn("font-mono text-sm font-black truncate", v.avg24 > 0 ? "text-green-400" : v.avg24 < 0 ? "text-red-400" : "text-slate-300")}>
                          {fmt.pct(v.avg24, 1)}
                        </span>
                        <span className="text-[8px] text-slate-500 font-mono">7D {fmt.pct(v.avg7d, 1)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Controls & Mode */}
              <div className="flex flex-col gap-5">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-[#bd93f9]" />
                  Settings
                </h3>
                
                <div className="flex flex-col gap-2.5">
                  <label className="font-mono text-[8px] text-slate-500 uppercase tracking-[0.3em] pl-1">점수 필터</label>
                  <div className="flex gap-1.5">
                    {[0, 30, 50, 70].map(score => (
                      <button
                        key={score}
                        onClick={() => setMinScore(score)}
                        className={cn(
                          "flex-1 py-1 rounded-md border font-mono text-[9px] transition-all",
                          minScore === score
                            ? "bg-[#bd93f9] text-background border-[#bd93f9] font-bold shadow-[0_0_10px_rgba(189,147,249,0.2)]"
                            : "bg-white/5 border-white/10 text-slate-400 hover:text-slate-200"
                        )}
                      >
                        {score === 0 ? "ALL" : `${score}+`}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Legend */}
              <div className="flex flex-col gap-2.5">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-red-400" />
                  Legend
                </h3>
                <div className="grid grid-cols-2 gap-y-2 gap-x-3 p-3 bg-white/5 border border-white/10 rounded-lg">
                  {SIGNAL_META.map(({ key, emoji, name }) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-sm">{emoji}</span>
                      <span className="font-mono text-[8px] text-slate-500 uppercase tracking-widest">{name}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          }
        />
      </PageLayout.Side>

      <PageLayout.Main>
        <PageHeader
          isLoading={loading}
          statusText={dashboardProgress ? `${dashboardProgress.active_improvements}개 개선 진행` : 'System Live'}
          statusColor={(dashboardProgress?.active_improvements || 0) > 0 ? "blue" : "green"}
          extra={
            <div className="flex items-center gap-5 font-mono text-[11px] text-muted-foreground mr-2">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "w-2 h-2 rounded-full shadow-lg",
                    loading ? "bg-amber-400 shadow-amber-400/50 animate-pulse" :
                      error ? "bg-red-400 shadow-red-400/50" :
                        "bg-green-400 shadow-green-400/50 animate-pulse"
                  )}
                />
                <span className="hidden sm:inline">{loading ? "스캔 중" : error ? "오류" : "LIVE"}</span>
              </div>
              <span className="hidden sm:inline">UPD {mounted && (lastUpdate ? fmt.time(lastUpdate) : (clock ? fmt.time(clock) : "--:--:--"))}</span>
              <Button
                variant="outline"
                size="sm"
                className="h-8 px-3 font-mono text-[10px] tracking-[0.1em] uppercase bg-white/5 border-white/10 hover:border-cyan-500/50 hover:text-cyan-400 transition-all"
                onClick={runPipeline}
                disabled={loading}
              >
                <RefreshCw className={cn("w-3 h-3 mr-1.5", loading && "animate-spin")} />
                <span className="hidden md:inline">새로고침</span>
              </Button>
            </div>
          }
        />

        <div className="min-h-screen bg-transparent text-white/90 relative px-6 py-6 md:px-10 md:py-8">
          {/* Background gradient - Standard Chimera Glow */}
          <div className="fixed inset-0 pointer-events-none z-0">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_1200px_800px_at_0%_0%,rgba(139,92,246,0.06),transparent)]" />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(189,147,249,0.04),transparent)]" />
          </div>

          <div className="relative z-10 max-w-[1800px] mx-auto flex flex-col gap-6">

            {/* Top Bar for Table Only */}
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-3 mb-1">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-black tracking-[-0.02em] text-white/90">
                  TOP CANDIDATES
                </h2>
                <div className="px-1.5 py-0.5 bg-white/5 rounded border border-white/10">
                  <span className="font-mono text-[9px] text-slate-500 font-bold tracking-[0.2em]">
                    {displayCandidates.length} / {candidates.length}
                  </span>
                </div>
              </div>

              {/* Mode Buttons moved back to Main */}
              <div className="flex items-center gap-2">
                <div className="flex gap-px bg-white/5 border border-white/10 rounded-md overflow-hidden">
                  {["momentum", "breakout", "reversal", "compression"].map(m => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={cn(
                        "px-3 py-1.5 font-mono text-[9px] tracking-[0.15em] uppercase transition-all whitespace-nowrap",
                        mode === m
                          ? "bg-[#bd93f9] text-background font-black"
                          : "text-slate-500 hover:bg-white/10 hover:text-slate-300"
                      )}
                    >
                      {m === "momentum" ? "모멘텀" : m === "breakout" ? "브레이크아웃" : m === "reversal" ? "반전" : "압축"}
                    </button>
                  ))}
                </div>
                
                <button
                  onClick={() => setRegimeAdaptive(!regimeAdaptive)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-[9px] tracking-[0.15em] uppercase transition-all border",
                    regimeAdaptive
                      ? "bg-[#bd93f9]/10 border-[#bd93f9]/30 text-[#bd93f9] shadow-[0_0_10px_rgba(189,147,249,0.1)]"
                      : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300"
                  )}
                >
                  <Zap className={cn("w-3 h-3", regimeAdaptive && "text-[#bd93f9]")} />
                  <span className="hidden xl:inline">ADAPTIVE</span>
                </button>
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 font-mono text-sm text-red-400">
                ⚠ {error}
              </div>
            )}

            {/* Table */}
            <div className="border border-white/10 rounded-xl overflow-hidden bg-white/[0.02] backdrop-blur-xl shadow-2xl">
              <div className="overflow-x-auto no-scrollbar">
                <table className="w-full">
                  <thead className="bg-secondary/50">
                    <tr>
                      <th className="px-3 py-4 text-left font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">#</th>
                      <th className="px-3 py-4 text-left font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">심볼</th>
                      <th className="px-3 py-4 text-right font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">가격</th>
                      <th className="px-3 py-4 text-right font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">24h</th>
                      <th className="px-3 py-4 text-right font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase hidden md:table-cell">RS</th>
                      <th className="px-3 py-4 text-right font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase hidden md:table-cell">VOL</th>
                      <th className="px-3 py-4 text-right font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase hidden md:table-cell">펀딩</th>
                      <th className="px-3 py-4 text-right font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase hidden md:table-cell">ΔOI</th>
                      <th className="px-3 py-4 text-right font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">스코어</th>
                      <th className="px-3 py-4 text-left font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase">시그널</th>
                      <th className="px-3 py-4"></th>
                      <th className="px-3 py-4"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && candidates.length === 0 ? (
                      <tr>
                        <td colSpan={12} className="py-16 text-center">
                          <div className="font-mono text-lg italic text-muted-foreground mb-2">데이터 수집 중…</div>
                          <div className="font-mono text-[11px] tracking-[0.15em] text-muted-foreground uppercase">{loadProgress}</div>
                        </td>
                      </tr>
                    ) : displayCandidates.length === 0 ? (
                      <tr>
                        <td colSpan={12} className="py-16 text-center font-mono text-lg italic text-muted-foreground">
                          조건에 맞는 종목 없음
                        </td>
                      </tr>
                    ) : (
                      displayCandidates.map((c, i) => (
                        <CandidateRow
                          key={c.symbol}
                          candidate={c}
                          rank={i + 1}
                          btcChange24={btcData?.change24 || 0}
                          expanded={expandedSym === c.symbol}
                          onToggle={() => setExpandedSym(expandedSym === c.symbol ? null : c.symbol)}
                          topSectors={topSectors}
                          botSectors={botSectors}
                          regimeLabel={regimeLabel}
                          regimeAdaptive={regimeAdaptive}
                        />
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Footer */}
            <footer className="mt-7 pt-4 border-t border-border/30 flex flex-wrap justify-between items-center gap-3 font-mono text-[10px] tracking-[0.15em] text-muted-foreground uppercase">
              <div>나혼자 스캐너 · v1.5 · Binance Futures Public API</div>
              <div>Next refresh: ~{mounted && lastUpdate ? fmt.time(new Date(lastUpdate.getTime() + CONFIG.AUTO_REFRESH_MS)) : "—"}</div>
            </footer>
          </div>
        </div>
      </PageLayout.Main>
    </PageLayout>
  )
}

// Sub-components
function RegimeCell({
  label,
  value,
  valueClass,
  note,
  noteColor
}: {
  label: string
  value: string
  valueClass?: string
  note: string
  noteColor?: string
}) {
  return (
    <div className="bg-card/50 backdrop-blur-sm px-4 py-3 flex flex-col gap-1">
      <div className="font-mono text-[10px] tracking-[0.2em] text-muted-foreground uppercase">{label}</div>
      <div className={cn("font-mono text-lg font-medium tabular-nums", valueClass)}>{value}</div>
      <div className={cn("text-[10px] text-muted-foreground", noteColor)}>{note}</div>
    </div>
  )
}

function CandidateRow({
  candidate: c,
  rank,
  btcChange24,
  expanded,
  onToggle,
  topSectors,
  botSectors,
  regimeLabel,
  regimeAdaptive
}: {
  candidate: Candidate
  rank: number
  btcChange24: number
  expanded: boolean
  onToggle: () => void
  topSectors: Set<string>
  botSectors: Set<string>
  regimeLabel: string
  regimeAdaptive: boolean
}) {
  const rs = c.change24 - btcChange24

  return (
    <>
      <tr className="border-b border-white/5 hover:bg-white/[0.04] transition-colors group">
        <td className="px-3 py-3 font-mono text-[10px] text-slate-500/60 tracking-[0.1em]">
          {String(rank).padStart(2, "0")}
        </td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[13px] font-bold text-white/90">{c.symbol.replace("USDT", "")}</span>
            {c.pumpFlagged && (
              <span className="px-1 py-0.5 text-[8px] font-mono font-black tracking-[0.2em] bg-red-500/15 text-red-500 border border-red-500/20 rounded-sm">PUMP</span>
            )}
          </div>
          <div className="font-mono text-[9px] text-slate-600 font-bold tracking-[0.2em] uppercase mt-0.5">
            {c.sector || "—"}
            {topSectors.has(c.sector) && <span className="text-green-500"> ▲</span>}
            {botSectors.has(c.sector) && <span className="text-red-500"> ▼</span>}
          </div>
        </td>
        <td className="px-3 py-3 text-right font-mono text-[11px] font-medium tabular-nums text-slate-300">{fmt.price(c.price)}</td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] font-bold tabular-nums", c.change24 > 0 ? "text-green-400" : c.change24 < 0 ? "text-red-400" : "text-slate-500")}>
          {fmt.pct(c.change24, 2)}
        </td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell", rs > 0 ? "text-green-400" : rs < 0 ? "text-red-400" : "text-slate-600")}>
          {fmt.pct(rs, 1)}
        </td>
        <td className="px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell text-slate-600">
          {c.volRatio != null ? fmt.multiplier(c.volRatio) : "—"}
        </td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell", c.funding && c.funding > 0 ? "text-green-400" : c.funding && c.funding < 0 ? "text-red-400" : "text-slate-600")}>
          {c.funding != null ? (c.funding * 100).toFixed(4) + "%" : "—"}
        </td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell", c.oiChange24 && c.oiChange24 > 0 ? "text-green-400" : c.oiChange24 && c.oiChange24 < 0 ? "text-red-400" : "text-slate-600")}>
          {c.oiChange24 != null ? fmt.pct(c.oiChange24, 1) : "—"}
        </td>
        <td className="px-3 py-3 text-right">
          <div className="relative inline-flex items-center">
            <div
              className={cn(
                "absolute inset-0 rounded-sm -z-10 opacity-30",
                c.score >= 70 ? "bg-green-500/40 shadow-[0_0_10px_rgba(34,211,238,0.15)]" :
                  c.score >= 40 ? "bg-amber-500/25" :
                    "bg-white/10"
              )}
              style={{ width: `${c.score}%` }}
            />
            <span className="font-mono text-[11px] font-black tabular-nums px-2 py-0.5 text-white/90">{c.score.toFixed(0)}</span>
          </div>
        </td>
        <td className="px-3 py-3">
          <div className="flex gap-1 flex-wrap">
            {SIGNAL_META.filter(({ key }) => c.signals[key]?.score > 40).map(({ key, emoji }) => (
              <span
                key={key}
                className="inline-flex items-center justify-center w-5 h-5 text-xs bg-white/5 border border-white/10 rounded-sm cursor-help hover:bg-white/10 transition-colors"
                title={`${SIGNAL_META.find(s => s.key === key)?.name} ${c.signals[key].score.toFixed(0)} ${c.signals[key].note ? "· " + c.signals[key].note : ""}`}
              >
                {emoji}
              </span>
            ))}
            {SIGNAL_META.filter(({ key }) => c.signals[key]?.score > 40).length === 0 && (
              <span className="text-muted-foreground/30 text-[10px] tracking-[0.1em]">—</span>
            )}
          </div>
        </td>
        <td className="px-3 py-3">
          <button
            onClick={onToggle}
            className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground hover:text-cyan-400 transition-colors px-2 py-1 flex items-center gap-1.5"
          >
            {expanded ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
            {expanded ? "CLOSE" : "INFO"}
          </button>
        </td>
        <td className="px-3 py-3">
          <a
            href={`https://www.tradingview.com/chart/?symbol=BINANCE:${c.symbol}.P`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-2 py-1 font-mono text-[9px] tracking-[0.1em] uppercase text-muted-foreground/60 border border-white/5 rounded-sm hover:text-cyan-400 hover:border-cyan-500/30 transition-all"
          >
            <ExternalLink className="w-2.5 h-2.5" />
          </a>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-white/[0.01]">
          <td colSpan={12} className="px-6 py-6 border-b border-white/5">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 mb-6">
              <DetailBox label="24h RANGE" value={`${fmt.price(c.low24)} → ${fmt.price(c.high24)}`} />
              <DetailBox label="24h VOLUME" value={`${(c.quoteVolume / 1_000_000).toFixed(1)}M`} />
              <DetailBox label="7d CHANGE" value={c.change7d != null ? fmt.pct(c.change7d) : "—"} />
              <DetailBox label="1h / 4h" value={`${fmt.pct(c.change1h || 0, 2)} / ${fmt.pct(c.change4h || 0, 2)}`} />
              <DetailBox label="SIGNALS" value={`${c.strongCount} ACTIVE`} />
              <DetailBox label="NARRATIVE" value={c.narrativeMult > 1 ? `+${((c.narrativeMult - 1) * 100).toFixed(0)}%` : c.narrativeMult < 1 ? `-${((1 - c.narrativeMult) * 100).toFixed(0)}%` : "NEUTRAL"} />
              <DetailBox label="SECTOR" value={c.sector || "—"} />
              <DetailBox label="REGIME" value={regimeLabel} />
            </div>
            <div className="border-t border-white/5 pt-5">
              <div className="font-mono text-[9px] tracking-[0.3em] text-muted-foreground/40 uppercase mb-4 pl-1">Signal Breakdown</div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4">
                {SIGNAL_META.map(({ key, emoji, name, color }) => (
                  <SignalBar key={key} label={`${emoji} ${name}`} value={c.signals[key].score} note={c.signals[key].note} color={color} />
                ))}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function SideStat({ label, value, note, noteColor }: { label: string; value: string; note: string; noteColor?: string }) {
  return (
    <div className="bg-white/[0.03] border border-white/5 rounded-lg px-3 py-2 flex flex-col gap-0.5">
      <div className="font-mono text-[8px] tracking-[0.2em] text-muted-foreground uppercase">{label}</div>
      <div className="font-mono text-[11px] font-bold text-foreground/90 truncate">{value}</div>
      <div className={cn("font-mono text-[9px] font-medium opacity-80", noteColor || "text-muted-foreground")}>{note}</div>
    </div>
  )
}

function DetailBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-3 py-2 bg-white/[0.02] border border-white/5 rounded flex flex-col gap-0.5">
      <div className="font-mono text-[8px] tracking-[0.2em] text-muted-foreground uppercase">{label}</div>
      <div className="font-mono text-[10px] font-bold text-foreground/80 truncate">{value}</div>
    </div>
  )
}

function SignalBar({ label, value, note, color }: { label: string; value: number; note?: string; color: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-3 font-mono text-[10px]">
        <span className="text-muted-foreground/50 uppercase tracking-widest w-24 truncate">{label}</span>
        <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, backgroundColor: color, opacity: 0.6 }} />
        </div>
        <span className="text-foreground/70 w-8 text-right font-black">{value.toFixed(0)}</span>
      </div>
      {note && <div className="text-[9px] text-muted-foreground/40 pl-[108px] truncate leading-none">{note}</div>}
    </div>
  )
}
