"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    CandlestickSeries,
    ColorType,
    createChart,
    type CandlestickData,
    type IChartApi,
    type ISeriesApi,
    type Time,
} from "lightweight-charts";
import { FiMaximize2, FiTrendingDown, FiTrendingUp } from "react-icons/fi";

import { fetchWithBypass } from "@/lib/api";

type ChartTimeFrame = "1m" | "5m" | "15m" | "1h" | "4h";

interface CandlestickChartProps {
    pair: string;
    timeFrame: ChartTimeFrame;
    isActive: boolean;
    onClick: () => void;
    compact?: boolean;
}

interface CandleData {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

function isSameCandle(a: CandleData | undefined, b: CandleData | undefined): boolean {
    if (!a || !b) return false;
    return (
        a.time === b.time &&
        a.open === b.open &&
        a.high === b.high &&
        a.low === b.low &&
        a.close === b.close
    );
}

type OhlcvResponse = {
    success?: boolean;
    candles?: Array<{
        timestamp: string;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number;
    }>;
};

function formatPrice(price: number, pair: string): string {
    if (!Number.isFinite(price)) return "-";
    if (pair.includes("XRP")) return price.toFixed(4);
    if (price >= 1000) return price.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return price.toFixed(2);
}

function formatClock(seconds: number, compact: boolean): string {
    const date = new Date(seconds * 1000);
    if (compact) {
        return date.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Seoul" });
    }
    return date.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: true, timeZone: "Asia/Seoul" });
}

function normalizePair(pair: string): string {
    const normalized = pair.toUpperCase().replace("/", "").replace(".P", "").replace(/\s+/g, "");
    return normalized.endsWith("USDT") ? normalized : `${normalized}USDT`;
}

function toSeriesData(rows: CandleData[]): CandlestickData<Time>[] {
    return rows.map((row) => ({
        time: row.time as Time,
        open: row.open,
        high: row.high,
        low: row.low,
        close: row.close,
    }));
}

function mergeSnapshot(prev: CandleData[], nextRows: CandleData[]): CandleData[] {
    if (nextRows.length === 0) return prev;
    if (prev.length === 0) return nextRows.slice(-320);

    const byTime = new Map<number, CandleData>();
    for (const row of prev) byTime.set(row.time, row);
    for (const row of nextRows) byTime.set(row.time, row);

    const merged = Array.from(byTime.values()).sort((a, b) => a.time - b.time);
    return merged.length > 320 ? merged.slice(merged.length - 320) : merged;
}

function upsertCandle(prev: CandleData[], next: CandleData): CandleData[] {
    if (prev.length === 0) return [next];
    const last = prev[prev.length - 1];
    if (last.time === next.time) {
        return [...prev.slice(0, -1), next];
    }
    if (last.time < next.time) {
        const merged = [...prev, next];
        return merged.length > 320 ? merged.slice(merged.length - 320) : merged;
    }
    return prev;
}

export default function CandlestickChart({
    pair,
    timeFrame,
    isActive,
    onClick,
    compact = false,
}: CandlestickChartProps) {
    const [data, setData] = useState<CandleData[]>([]);
    const [hoveredData, setHoveredData] = useState<CandleData | null>(null);
    const [error, setError] = useState("");

    const containerRef = useRef<HTMLDivElement | null>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const resizeObserverRef = useRef<ResizeObserver | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<number | null>(null);
    const hasFittedRef = useRef(false);
    const prevDataRef = useRef<CandleData[]>([]);
    const lastWsMessageAtRef = useRef(0);

    const symbol = useMemo(() => normalizePair(pair), [pair]);

    const refreshMs = useMemo(() => {
        const map: Record<ChartTimeFrame, number> = {
            "1m": 12_000,
            "5m": 20_000,
            "15m": 25_000,
            "1h": 35_000,
            "4h": 45_000,
        };
        return map[timeFrame] || 30_000;
    }, [timeFrame]);

    const loadHistorical = useCallback(async () => {
        const parseRows = (source: Array<Array<string | number>>): CandleData[] => {
            return source
                .map((row) => ({
                    time: Math.floor(Number(row[0]) / 1000),
                    open: Number(row[1]),
                    high: Number(row[2]),
                    low: Number(row[3]),
                    close: Number(row[4]),
                    volume: Number(row[5] || 0),
                }))
                .filter((row) => row.time > 0 && row.open > 0 && row.high > 0 && row.low > 0 && row.close > 0);
        };

        try {
            const binanceRes = await fetch(
                `https://fapi.binance.com/fapi/v1/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(timeFrame)}&limit=240`,
            );
            if (binanceRes.ok) {
                const payload = (await binanceRes.json()) as Array<Array<string | number>>;
                if (Array.isArray(payload) && payload.length > 0) {
                    const parsed = parseRows(payload);
                    setData((prev) => mergeSnapshot(prev, parsed));
                    setError("");
                    return;
                }
            }
        } catch {
            // Fall through to backend fallback.
        }

        try {
            const params = new URLSearchParams({
                symbol: pair,
                timeframe: timeFrame,
                limit: "240",
            });
            const res = await fetchWithBypass(`/api/market/ohlcv?${params.toString()}`);
            const json = (await res.json()) as OhlcvResponse;
            if (!res.ok || !json?.success || !Array.isArray(json.candles)) {
                throw new Error("OHLCV fallback failed");
            }

            const rows = json.candles
                .map((c) => {
                    const ms = Date.parse(c.timestamp);
                    return {
                        time: Number.isFinite(ms) ? Math.floor(ms / 1000) : 0,
                        open: Number(c.open || 0),
                        high: Number(c.high || 0),
                        low: Number(c.low || 0),
                        close: Number(c.close || 0),
                        volume: Number(c.volume || 0),
                    };
                })
                .filter((row) => row.time > 0 && row.open > 0 && row.high > 0 && row.low > 0 && row.close > 0);
            setData((prev) => mergeSnapshot(prev, rows));
            setError("");
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load chart data");
        }
    }, [pair, symbol, timeFrame]);

    useEffect(() => {
        hasFittedRef.current = false;
        lastWsMessageAtRef.current = 0;
        void loadHistorical();
        const id = window.setInterval(() => {
            const now = Date.now();
            const wsQuietForMs = now - lastWsMessageAtRef.current;
            // WebSocket이 정상 수신 중이면 스냅샷 폴링을 건너뛰어 깜빡임을 줄인다.
            if (lastWsMessageAtRef.current > 0 && wsQuietForMs < refreshMs * 2) return;
            void loadHistorical();
        }, refreshMs);
        return () => {
            window.clearInterval(id);
        };
    }, [loadHistorical, refreshMs]);

    useEffect(() => {
        if (!containerRef.current) return;

        const chart = createChart(containerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: "transparent" },
                textColor: "#94a3b8",
                fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
                attributionLogo: false,
            },
            handleScale: {
                mouseWheel: true,
                pinch: true,
                axisPressedMouseMove: true,
            },
            handleScroll: {
                mouseWheel: true,
                pressedMouseMove: true,
                horzTouchDrag: true,
                vertTouchDrag: true,
            },
            grid: {
                vertLines: { color: "rgba(189, 147, 249, 0.03)" },
                horzLines: { color: "rgba(189, 147, 249, 0.03)" },
            },
            crosshair: {
                vertLine: { color: "#474D57", width: 1, style: 3 },
                horzLine: { color: "#474D57", width: 1, style: 3 },
            },
            rightPriceScale: {
                borderColor: "#2B3139",
            },
            timeScale: {
                borderColor: "#2B3139",
                timeVisible: true,
                secondsVisible: false,
            },
            width: containerRef.current.clientWidth,
            height: containerRef.current.clientHeight,
        });

        const series = chart.addSeries(CandlestickSeries, {
            upColor: "#6075ffff",
            downColor: "#ffa2f1ff",
            borderVisible: false,
            wickUpColor: "#6075ffff",
            wickDownColor: "#ffa2f1ff",
        });

        chart.subscribeCrosshairMove((param) => {
            const point = param.seriesData.get(series);
            if (!point || typeof point !== "object" || !("open" in point)) {
                setHoveredData(null);
                return;
            }
            const t = point.time;
            const time = typeof t === "number" ? t : Number(t);
            setHoveredData({
                time: Number.isFinite(time) ? time : 0,
                open: Number(point.open),
                high: Number(point.high),
                low: Number(point.low),
                close: Number(point.close),
                volume: 0,
            });
        });

        chartRef.current = chart;
        seriesRef.current = series;

        resizeObserverRef.current = new ResizeObserver((entries) => {
            if (!entries.length || !containerRef.current || !chartRef.current) return;
            const rect = entries[0].contentRect;
            chartRef.current.applyOptions({
                width: rect.width,
                height: rect.height,
            });
        });
        resizeObserverRef.current.observe(containerRef.current);

        return () => {
            resizeObserverRef.current?.disconnect();
            resizeObserverRef.current = null;
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
        };
    }, []);

    useEffect(() => {
        if (!seriesRef.current || data.length === 0) return;

        const prev = prevDataRef.current;
        const last = data[data.length - 1];
        const prevLast = prev[prev.length - 1];
        let handledByIncrementalUpdate = false;

        if (prev.length > 0) {
            const sameHead = data[0]?.time === prev[0]?.time;
            const samePreviousBar = isSameCandle(
                data.length >= 2 ? data[data.length - 2] : undefined,
                prev.length >= 2 ? prev[prev.length - 2] : undefined,
            );

            const updatedSameBar =
                data.length === prev.length &&
                sameHead &&
                samePreviousBar &&
                last.time === prevLast?.time;

            const appendedNextBar =
                data.length === prev.length + 1 &&
                sameHead &&
                isSameCandle(data[data.length - 2], prevLast);

            if (updatedSameBar || appendedNextBar) {
                seriesRef.current.update({
                    time: last.time as Time,
                    open: last.open,
                    high: last.high,
                    low: last.low,
                    close: last.close,
                });
                handledByIncrementalUpdate = true;
            }
        }

        if (!handledByIncrementalUpdate) {
            seriesRef.current.setData(toSeriesData(data));
            if (!hasFittedRef.current) {
                chartRef.current?.timeScale().fitContent();
                hasFittedRef.current = true;
            }
        }

        prevDataRef.current = data;
    }, [data]);

    useEffect(() => {
        let unmounted = false;

        const connect = () => {
            const ws = new WebSocket(`wss://fstream.binance.com/ws/${symbol.toLowerCase()}@kline_${timeFrame}`);
            wsRef.current = ws;

            ws.onmessage = (event) => {
                if (unmounted) return;
                try {
                    const payload = JSON.parse(event.data) as { k?: Record<string, string | number> };
                    const kline = payload.k;
                    if (!kline) return;
                    lastWsMessageAtRef.current = Date.now();

                    const next: CandleData = {
                        time: Math.floor(Number(kline.t) / 1000),
                        open: Number(kline.o),
                        high: Number(kline.h),
                        low: Number(kline.l),
                        close: Number(kline.c),
                        volume: Number(kline.v || 0),
                    };
                    if (!next.time || next.open <= 0 || next.high <= 0 || next.low <= 0 || next.close <= 0) return;

                    setData((prev) => upsertCandle(prev, next));
                } catch {
                    // Ignore malformed frame.
                }
            };

            ws.onerror = () => {
                try {
                    ws.close();
                } catch {
                    // Ignore close error.
                }
            };

            ws.onclose = () => {
                if (unmounted) return;
                void loadHistorical();
                reconnectTimerRef.current = window.setTimeout(connect, 3000);
            };
        };

        connect();

        return () => {
            unmounted = true;
            if (reconnectTimerRef.current) {
                window.clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
            wsRef.current?.close();
            wsRef.current = null;
        };
    }, [loadHistorical, symbol, timeFrame]);

    const currentPrice = data.at(-1)?.close ?? 0;
    const openPrice = data.at(0)?.open ?? currentPrice;
    const priceChange = currentPrice - openPrice;
    const priceChangePercent = openPrice > 0 ? (priceChange / openPrice) * 100 : 0;
    const isPositive = priceChangePercent >= 0;

    const dayHigh = useMemo(() => (data.length ? Math.max(...data.map((d) => d.high)) : currentPrice), [data, currentPrice]);
    const dayLow = useMemo(() => (data.length ? Math.min(...data.map((d) => d.low)) : currentPrice), [data, currentPrice]);
    const dayVol = useMemo(() => data.reduce((sum, d) => sum + Number(d.volume || 0), 0), [data]);

    return (
        <div
            className={`relative h-full cursor-pointer overflow-hidden transition-all duration-300 ${isActive ? "shadow-[0_0_10px_rgba(255,255,255,0.04)]" : ""}`}
            onClick={onClick}
        >
            <div ref={containerRef} className="absolute inset-0" />

            <div className={`pointer-events-none absolute inset-x-0 top-0 z-10 bg-gradient-to-b from-black/35 via-black/10 to-transparent ${compact ? "p-3" : "p-4"}`}>
                <div className="flex items-start gap-3">
                    <div className={`flex items-center justify-center w-8 h-8 rounded-lg ${isPositive ? "bg-emerald-200/10" : "bg-rose-200/10"}`}>
                        {isPositive ? <FiTrendingUp className="text-emerald-200/70" /> : <FiTrendingDown className="text-rose-200/70" />}
                    </div>
                    <div>
                        <h3 className={`font-bold text-slate-100 ${compact ? "text-sm" : "text-base"}`}>
                            {pair} · {timeFrame.toUpperCase()} · ${formatPrice(currentPrice, pair)}
                            <span className={`ml-2 text-xs font-semibold ${isPositive ? "text-emerald-200/80" : "text-rose-200/80"}`}>
                                {isPositive ? "+" : ""}
                                {priceChangePercent.toFixed(2)}%
                            </span>
                        </h3>
                        <p className="text-xs text-slate-500">{error ? `Feed: reconnecting (${error})` : "Feed: live websocket"}</p>
                    </div>
                </div>

                <div className="mt-1 h-4">
                    {hoveredData ? (
                        <div className="flex items-center gap-4 text-[10px] text-slate-400">
                            <span>
                                T <span className="text-slate-200">{formatClock(hoveredData.time, compact)}</span>
                            </span>
                            <span>
                                O <span className="text-slate-200">{formatPrice(hoveredData.open, pair)}</span>
                            </span>
                            <span>
                                H <span className="text-emerald-200/80">{formatPrice(hoveredData.high, pair)}</span>
                            </span>
                            <span>
                                L <span className="text-rose-200/80">{formatPrice(hoveredData.low, pair)}</span>
                            </span>
                            <span>
                                C{" "}
                                <span className={hoveredData.close >= hoveredData.open ? "text-emerald-200/80" : "text-rose-200/80"}>
                                    {formatPrice(hoveredData.close, pair)}
                                </span>
                            </span>
                        </div>
                    ) : null}
                </div>
            </div>

            {!compact && (
                <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 p-3 bg-gradient-to-t from-black/45 via-black/18 to-transparent">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                        <div className="flex items-center gap-4">
                            <span>
                                24h Vol: <span className="text-slate-300">{dayVol.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                            </span>
                            <span>
                                24h High: <span className="text-emerald-200/80">${formatPrice(dayHigh, pair)}</span>
                            </span>
                            <span>
                                24h Low: <span className="text-rose-200/80">${formatPrice(dayLow, pair)}</span>
                            </span>
                        </div>
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded border border-white/[0.08] bg-white/[0.04] text-slate-300">
                            <FiMaximize2 className="text-xs" />
                            Full
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
