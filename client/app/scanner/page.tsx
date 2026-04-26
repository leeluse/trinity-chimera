"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
import { RefreshCw, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  PageLayout,
  PageHeader,
  CandidateRow
} from "@/components"
import { AppRightPanel } from "@/components/layout/AppRightPanel"
import { useDashboardQueries } from "@/hooks/useDashboardQueries"
import { useMarketGlobal } from "@/hooks/useMarketGlobal"
import { useLiquidationStream } from "@/hooks/useLiquidationStream"
import { MarketGlobalBar } from "@/components/features/scanner/MarketGlobalBar"
import { PreSignalPanel } from "@/components/features/scanner/PreSignalPanel"
import { NAMES } from "@/constants"


// Modular Components
import { SideStat } from "@/components/shared/SideStat"

// Shared Types & Utils & Constants
import { CONFIG, SIGNAL_META, MODE_WEIGHTS } from "./constants"
import { Candidate, Ticker, SectorData, Signal } from "./types"
import { fmt, fetchJson, sleep, getSector } from "./utils"
import { sigMomentum, sigVolume, sigBreakout, sigCompression, sigFunding, sigOI, sigCapitulation, sigEarly, sigFlow, sigVolSurge } from "./scannerLogic"

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
    logsIntervalMs: 8000
  })

  const marketGlobal = useMarketGlobal();
  const liqStream = useLiquidationStream();

  const runtimeAgentIds = useMemo(() => {
    if (bots && bots.length > 0) return bots.map((b: any) => b.id).sort()
    return []
  }, [bots])

  const agentNames = useMemo(() => {
    return runtimeAgentIds.map((id, idx) => {
      const bot = bots.find((b: any) => b.id === id)
      if (bot) return bot.name
      return NAMES[idx] || "Agent " + (idx + 1)
    })
  }, [bots, runtimeAgentIds])

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
    const flowSig = sigFlow(
      token.funding ?? null,
      token.oiChange24 ?? null,
      token.lsRatio ?? null,
      token.takerRatio ?? null,
      token.change24
    )
    const signals: Record<string, Signal> = {
      momentum: sigMomentum(token, btc),
      volume: sigVolume(token),
      breakout: sigBreakout(token),
      compression: sigCompression(token),
      funding: sigFunding(token),
      oi: sigOI(token),
      capitulation: sigCapitulation(token),
      early: sigEarly(token),
      volSurge: sigVolSurge(token.candles5m),
      flow: flowSig,
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
      weightedSum += (signals[k].score * (weights as any)[k]) || 0
      totalWeight += (weights as any)[k] * 100
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
        fetchJson(`${CONFIG.API_BASE}/fapi/v1/ticker/24hr`) as Promise<any[]>,
        fetchJson(`${CONFIG.API_BASE}/fapi/v1/premiumIndex`) as Promise<any[]>,
      ])

      const fundingMap: Record<string, number> = {}
      fundingArr.forEach(f => { fundingMap[f.symbol] = parseFloat(f.lastFundingRate) })

      const filtered = (tickersRaw || [])
        .filter(t => t.symbol.endsWith("USDT") && !t.symbol.includes("_") && !/^(USDC|BUSD|FDUSD|DAI|TUSD|USDP)USDT$/.test(t.symbol) && parseFloat(t.quoteVolume) >= CONFIG.MIN_QUOTE_VOLUME)
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
      setBtcData(btc as Ticker); setEthData(eth as Ticker || null)

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
      setAvgFunding(totalVol > 0 ? weighted / totalVol : 0)

      let regime, note
      if (btc.change24 > 3 && upPct > 60) { regime = "RISK-ON"; note = "광범위 상승, 알트 추세 유리" }
      else if (btc.change24 < -3 && upPct < 40) { regime = "RISK-OFF"; note = "하락 체제, 숏 또는 관망" }
      else if (upPct > 55) { regime = "BROAD"; note = "섹터 로테이션 중" }
      else if (upPct < 45) { regime = "WEAK"; note = "약세 편향, 신중" }
      else { regime = "MIXED"; note = "혼조세, 개별 종목 선택적" }
      setRegimeLabel(regime); setRegimeNote(note)

      const phase2Set = new Map<string, Ticker>()
      filtered.slice(0, CONFIG.PHASE1_TOP_N).forEach(t => phase2Set.set(t.symbol, t as Ticker))
      filtered.filter(t => Math.abs(t.funding || 0) > 0.0003).forEach(t => phase2Set.set(t.symbol, t as Ticker))
      const phase2 = [...phase2Set.values()]

      setLoadProgress(`Phase 2: ${phase2.length}종목 심층 분석…`)
      for (let i = 0; i < phase2.length; i += CONFIG.BATCH_SIZE) {
        const slice = phase2.slice(i, i + CONFIG.BATCH_SIZE)
        await Promise.all(slice.map(async (t) => {
          try {
            const [dailyRaw, h1Close, oiHist, cd5mRaw, lsRaw, tkRaw] = await Promise.all([
              fetchJson(`${CONFIG.API_BASE}/fapi/v1/klines?symbol=${t.symbol}&interval=1d&limit=30`).catch(() => null),
              fetchJson(`${CONFIG.API_BASE}/fapi/v1/klines?symbol=${t.symbol}&interval=1h&limit=60`).then((k: any) => Array.isArray(k) ? k.map((c: any) => parseFloat(String(c[4]))) : []).catch(() => []),
              fetchJson(`${CONFIG.API_BASE}/futures/data/openInterestHist?symbol=${t.symbol}&period=1h&limit=24`).then((o: any) => Array.isArray(o) ? o.map((x: any) => parseFloat(x.sumOpenInterest)) : []).catch(() => []),
              fetchJson(`${CONFIG.API_BASE}/fapi/v1/klines?symbol=${t.symbol}&interval=5m&limit=35`).catch(() => null),
              fetchJson(`${CONFIG.API_BASE}/futures/data/globalLongShortAccountRatio?symbol=${t.symbol}&period=5m&limit=1`).catch(() => null),
              fetchJson(`${CONFIG.API_BASE}/futures/data/takerlongshortRatio?symbol=${t.symbol}&period=5m&limit=6`).catch(() => null),
            ])
            if (cd5mRaw && Array.isArray(cd5mRaw)) {
              t.candles5m = (cd5mRaw as any[]).map((c: any) => ({
                o: +c[1], h: +c[2], l: +c[3], c: +c[4], v: +c[5], buyVol: +c[9], quoteVol: +c[7],
              }));
            }
            if (lsRaw && Array.isArray(lsRaw) && (lsRaw as any[]).length > 0) {
              t.lsRatio = parseFloat((lsRaw as any[])[0]?.longShortRatio ?? "1");
            }
            if (tkRaw && Array.isArray(tkRaw) && (tkRaw as any[]).length > 0) {
              const vals = (tkRaw as any[]).map((x: any) => parseFloat(x.buySellRatio));
              t.takerRatio = vals.reduce((s, v) => s + v, 0) / vals.length;
            }
            if (dailyRaw && Array.isArray(dailyRaw)) {
              t.dailyCloses = dailyRaw.map((c: any) => parseFloat(String(c[4])))
              const quoteVols = dailyRaw.map((c: any) => parseFloat(String(c[7])))
              if (quoteVols.length >= 4) t.volRatio = quoteVols[quoteVols.length - 1] / (quoteVols.slice(-8, -1).reduce((a: any, b: any) => a + b, 0) / 7)
              if (t.dailyCloses && t.dailyCloses.length >= 8) t.change7d = (t.dailyCloses[t.dailyCloses.length - 1] - t.dailyCloses[t.dailyCloses.length - 8]) / t.dailyCloses[t.dailyCloses.length - 8] * 100
            }
            t.hourlyCloses = h1Close
            if (h1Close && h1Close.length >= 5) {
              t.change1h = (h1Close[h1Close.length - 1] - h1Close[h1Close.length - 2]) / h1Close[h1Close.length - 2] * 100
              t.change4h = (h1Close[h1Close.length - 1] - h1Close[h1Close.length - 5]) / h1Close[h1Close.length - 5] * 100
            }
            if (oiHist && oiHist.length >= 20) t.oiChange24 = (oiHist[oiHist.length - 1] - oiHist[0]) / oiHist[0] * 100
          } catch { /* skip */ }
        }))
        setLoadProgress(`Phase 2: ${Math.min(i + CONFIG.BATCH_SIZE, phase2.length)}/${phase2.length} 분석 중…`)
        if (i + CONFIG.BATCH_SIZE < phase2.length) await sleep(CONFIG.BATCH_DELAY_MS)
      }

      const bySector: Record<string, SectorData> = {}
      phase2.forEach(t => {
        const s = getSector(t.symbol); if (s === "—") return
        if (!bySector[s]) bySector[s] = { tokens: [], sum24: 0, sum7d: 0, count: 0, avg24: 0, avg7d: 0, momentum: 0 }
        bySector[s].tokens.push(t.symbol); bySector[s].sum24 += t.change24; bySector[s].sum7d += (t.change7d || 0); bySector[s].count++
      })
      for (const s in bySector) { const v = bySector[s]; v.avg24 = v.sum24 / v.count; v.avg7d = v.sum7d / v.count; v.momentum = v.avg24 + v.avg7d * 0.4 }
      const ranked = Object.entries(bySector).filter(([, v]) => v.count >= 2).sort((a, b) => b[1].momentum - a[1].momentum) as [string, SectorData][]
      setSectorMomentum({ ranked })
      setTopSectors(new Set(ranked.slice(0, 3).map(([name]) => name))); setBotSectors(new Set(ranked.slice(-2).map(([name]) => name)))

      const scored = phase2
        .filter(t => t.symbol !== CONFIG.BTC_SYMBOL && t.symbol !== CONFIG.ETH_SYMBOL)
        .map(t => {
          const res = computeComposite(t, btc as Ticker, mode, regime, new Set(ranked.slice(0, 3).map(([n]) => n)), new Set(ranked.slice(-2).map(([n]) => n)))
          return { ...t, ...res } as Candidate
        }).sort((a, b) => b.score - a.score)

      setCandidates(scored); setLastUpdate(new Date())
    } catch (e) { setError(`스캔 실패: ${e instanceof Error ? e.message : "오류"}`) } finally { setLoading(false) }
  }, [mode, computeComposite])

  useEffect(() => { runPipeline(); const interval = setInterval(runPipeline, CONFIG.AUTO_REFRESH_MS); return () => clearInterval(interval) }, [runPipeline])

  const displayCandidates = useMemo(() => candidates.filter(c => c.score >= minScore).slice(0, CONFIG.TOP_N_DISPLAY), [candidates, minScore])

  return (
    <PageLayout rightWidth="lg:w-[420px]">
      <PageLayout.Side>
        <AppRightPanel
          agentIds={runtimeAgentIds}
          names={agentNames}
          metricsData={metricsData}
          evolutionEvents={evolutionEvents}
          decisionLogs={decisionLogs}
          botTrades={botTrades}
          automationStatus={automationStatus}
          onToggleAutomation={toggleAutomation}
          scannerContent={
            <div className="flex flex-col gap-8 p-6 pb-20">
              <MarketGlobalBar global={marketGlobal} liq={liqStream} />
              <div className="flex flex-col gap-3">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-primary" /> Market Regime
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <SideStat label="BTC" value={`$${fmt.price(btcData?.price)}`} note={fmt.pct(btcData?.change24)} noteColor={btcData && btcData.change24 > 0 ? "text-green-400" : "text-red-400"} />
                  <SideStat label="ETH" value={`$${fmt.price(ethData?.price)}`} note={fmt.pct(ethData?.change24)} noteColor={ethData && ethData.change24 > 0 ? "text-green-400" : "text-red-400"} />
                  <SideStat label="AVG FUND" value={`${(avgFunding * 100).toFixed(4)}%`} note={avgFunding > 0.0002 ? "숏 전환" : avgFunding < -0.0001 ? "롱 전환" : "중립"} />
                  <SideStat label="BREADTH" value={`${breadth.up}/${breadth.down}`} note={`상승 ${breadth.pct.toFixed(0)}%`} />
                </div>
                <div className="bg-white/5 border border-white/10 rounded-lg px-3 py-3 mt-1 backdrop-blur-md">
                  <div className="font-mono text-[8px] tracking-[0.3em] text-slate-500 uppercase mb-0.5">시장 체제</div>
                  <div className={cn("font-mono text-lg font-black mb-0.5 tracking-tight", regimeLabel === "RISK-ON" && "text-green-400", regimeLabel === "RISK-OFF" && "text-red-400", regimeLabel === "WEAK" && "text-amber-400")}>{regimeLabel}</div>
                  <div className="text-[10px] text-slate-400 leading-tight">{regimeNote} {regimeAdaptive && regimeLabel !== "MIXED" && "· ADAPTIVE ON"}</div>
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-accent" /> Sector Rotation
                </h3>
                <div className="flex flex-row flex-wrap gap-1.5">
                  {sectorMomentum?.ranked.map(([name, v]: [string, SectorData]) => (
                    <div key={name} className="flex-1 min-w-[100px] flex flex-col gap-1 p-2.5 bg-white/5 border border-white/10 rounded-md hover:bg-white/[0.08] transition-colors">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[8px] font-bold tracking-wider text-slate-500 uppercase">{name}</span>
                        <span className="text-[8px] text-slate-600 font-bold">{v.count}</span>
                      </div>
                      <div className="flex items-baseline justify-between">
                        <span className={cn("font-mono text-sm font-black truncate", v.avg24 > 0 ? "text-green-400" : v.avg24 < 0 ? "text-red-400" : "text-slate-300")}>{fmt.pct(v.avg24, 1)}</span>
                        <span className="text-[8px] text-slate-500 font-mono">7D {fmt.pct(v.avg7d, 1)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-5">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-primary" /> Settings
                </h3>
                <div className="flex flex-col gap-2.5">
                  <label className="font-mono text-[8px] text-slate-500 uppercase tracking-[0.3em] pl-1">점수 필터</label>
                  <div className="flex gap-1.5">
                    {[0, 30, 50, 70].map((score: number) => (
                      <button key={score} onClick={() => setMinScore(score)} className={cn("flex-1 py-1 rounded-md border font-mono text-[9px] transition-all", minScore === score ? "bg-primary text-background border-primary font-bold shadow-[0_0_10px_rgba(189,147,249,0.2)]" : "bg-white/5 border-white/10 text-slate-400 hover:text-slate-200")}>
                        {score === 0 ? "ALL" : `${score}+`}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2.5">
                <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
                  <div className="w-1 h-2.5 bg-red-400" /> Legend
                </h3>
                <div className="grid grid-cols-2 gap-y-2 gap-x-3 p-3 bg-white/5 border border-white/10 rounded-lg">
                  {SIGNAL_META.map(({ key, emoji, name }: { key: string; emoji: string; name: string }) => (
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
          isLoading={loading} statusText={dashboardProgress ? `${dashboardProgress.active_improvements}개 개선 진행` : 'System Live'}
          statusColor={(dashboardProgress?.active_improvements || 0) > 0 ? "blue" : "green"}
          extra={
            <div className="flex items-center gap-5 font-mono text-[11px] text-muted-foreground mr-2">
              <div className="flex items-center gap-2">
                <span className={cn("w-2 h-2 rounded-full shadow-lg", loading ? "bg-amber-400 shadow-amber-400/50 animate-pulse" : error ? "bg-red-400 shadow-red-400/50" : "bg-green-400 shadow-green-400/50 animate-pulse")} />
                <span className="hidden sm:inline">{loading ? "스캔 중" : error ? "오류" : "LIVE"}</span>
              </div>
              <span className="hidden sm:inline">UPD {mounted && (lastUpdate ? fmt.time(lastUpdate) : (clock ? fmt.time(clock) : "--:--:--"))}</span>
              <Button variant="outline" size="sm" className="h-8 px-3 font-mono text-[10px] tracking-[0.1em] uppercase bg-white/5 border-white/10 hover:border-cyan-500/50 hover:text-cyan-400 transition-all" onClick={runPipeline} disabled={loading}>
                <RefreshCw className={cn("w-3 h-3 mr-1.5", loading && "animate-spin")} /> <span className="hidden md:inline">새로고침</span>
              </Button>
            </div>
          }
        />

        <div className="min-h-screen bg-transparent text-white/90 relative px-6 py-6 md:px-10 md:py-8">
          <div className="fixed inset-0 pointer-events-none z-0">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_1200px_800px_at_0%_0%,rgba(139,92,246,0.06),transparent)]" />
          </div>

          <div className="relative z-10 flex flex-col gap-6 max-w-[1400px] mx-auto">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-baseline gap-3">
                <h1 className="text-2xl font-black tracking-tighter text-white uppercase italic">Top Candidates</h1>
                <span className="font-mono text-sm text-slate-500 font-bold bg-white/5 px-2 py-0.5 rounded border border-white/10">[{displayCandidates.length} / {candidates.length}]</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex gap-px bg-white/5 border border-white/10 rounded-md overflow-hidden">
                  {["momentum", "breakout", "reversal", "compression"].map((m: string) => (
                    <button key={m} onClick={() => setMode(m)} className={cn("px-3 py-1.5 font-mono text-[9px] tracking-[0.15em] uppercase transition-all whitespace-nowrap", mode === m ? "bg-primary text-background font-black" : "text-slate-500 hover:bg-white/10 hover:text-slate-300")}>
                      {m === "momentum" ? "모멘텀" : m === "breakout" ? "브레이크아웃" : m === "reversal" ? "반전" : "압축"}
                    </button>
                  ))}
                </div>
                <button onClick={() => setRegimeAdaptive(!regimeAdaptive)} className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-[9px] tracking-[0.15em] uppercase transition-all border", regimeAdaptive ? "bg-primary/10 border-primary/30 text-primary shadow-[0_0_10px_rgba(189,147,249,0.1)]" : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300")}>
                  <Zap className={cn("w-3 h-3", regimeAdaptive && "text-primary")} /> <span className="hidden xl:inline">ADAPTIVE</span>
                </button>
              </div>
            </div>

            {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 font-mono text-sm text-red-400">⚠ {error}</div>}

            <div className="border border-white/10 rounded-xl overflow-hidden bg-white/[0.02] backdrop-blur-xl shadow-2xl">
              <div className="overflow-x-auto no-scrollbar">
                <table className="w-full">
                  <thead className="bg-secondary/50">
                    <tr>
                      {["#", "심볼", "가격", "24h", "RS", "VOL", "펀딩", "ΔOI", "스코어", "시그널"].map((h: string, i: number) => (
                        <th key={h} className={cn("px-3 py-4 text-left font-mono text-[9px] font-medium tracking-[0.2em] text-muted-foreground uppercase", (i >= 2 && i <= 8) && "text-right", (i >= 4 && i <= 7) && "hidden md:table-cell")}>{h}</th>
                      ))}
                      <th className="px-3 py-4"></th><th className="px-3 py-4"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && candidates.length === 0 ? (
                      <tr><td colSpan={12} className="py-16 text-center"><div className="font-mono text-lg italic text-muted-foreground mb-2">데이터 수집 중…</div><div className="font-mono text-[11px] tracking-[0.15em] text-muted-foreground uppercase">{loadProgress}</div></td></tr>
                    ) : displayCandidates.length === 0 ? (
                      <tr><td colSpan={12} className="py-16 text-center font-mono text-lg italic text-muted-foreground">조건에 맞는 종목 없음</td></tr>
                    ) : (
                      displayCandidates.map((c: Candidate, i: number) => (
                        <CandidateRow key={c.symbol} candidate={c} rank={i + 1} btcChange24={btcData?.change24 || 0} expanded={expandedSym === c.symbol} onToggle={() => setExpandedSym(expandedSym === c.symbol ? null : c.symbol)} topSectors={topSectors} botSectors={botSectors} regimeLabel={regimeLabel} regimeAdaptive={regimeAdaptive} shortLiq5m={liqStream.bySymbol[c.symbol]?.shortLiq ?? 0} longLiq5m={liqStream.bySymbol[c.symbol]?.longLiq ?? 0} />
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {candidates.length > 0 && <PreSignalPanel candidates={displayCandidates} />}

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
