const FAPI = "https://fapi.binance.com/fapi/v1";

async function fetchJSON(url: string): Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function getBinanceSymbols(): Promise<string[]> {
  const data = await fetchJSON(`${FAPI}/exchangeInfo`);
  if (!data?.symbols) return [];
  return data.symbols
    .filter(
      (s: any) =>
        s.quoteAsset === "USDT" &&
        s.contractType === "PERPETUAL" &&
        s.status === "TRADING"
    )
    .map((s: any) => s.symbol as string);
}

export async function getBinanceTicker(
  symbol: string
): Promise<Record<string, string> | null> {
  return await fetchJSON(`${FAPI}/ticker/24hr?symbol=${symbol}`);
}

export async function getBinanceOI(
  symbol: string
): Promise<{ current: number; change1h: number; change4h: number; change24h: number }> {
  const fallback = { current: 0, change1h: 0, change4h: 0, change24h: 0 };
  const data = await fetchJSON(
    `${FAPI}/openInterestHist?symbol=${symbol}&period=1h&limit=25`
  );
  if (!Array.isArray(data) || data.length === 0) return fallback;

  const toNum = (item: any) => parseFloat(item.sumOpenInterest);
  const latest = toNum(data[0]);

  const pct = (past: number) =>
    past !== 0 ? ((latest - past) / past) * 100 : 0;

  const change1h = data[1] ? pct(toNum(data[1])) : 0;
  const change4h = data[4] ? pct(toNum(data[4])) : 0;
  const change24h = data[data.length - 1] ? pct(toNum(data[data.length - 1])) : 0;

  return { current: latest, change1h, change4h, change24h };
}

export async function getBinanceLSRatio(
  symbol: string
): Promise<{ longRatio: number; shortRatio: number; topLongRatio: number; topShortRatio: number }> {
  const fallback = { longRatio: 50, shortRatio: 50, topLongRatio: 50, topShortRatio: 50 };

  const [global, top] = await Promise.all([
    fetchJSON(`${FAPI}/globalLongShortAccountRatio?symbol=${symbol}&period=5m&limit=1`),
    fetchJSON(`${FAPI}/topLongShortAccountRatio?symbol=${symbol}&period=5m&limit=1`),
  ]);

  const longRatio =
    Array.isArray(global) && global[0]
      ? parseFloat(global[0].longAccount) * 100
      : 50;
  const shortRatio =
    Array.isArray(global) && global[0]
      ? parseFloat(global[0].shortAccount) * 100
      : 50;
  const topLongRatio =
    Array.isArray(top) && top[0] ? parseFloat(top[0].longAccount) * 100 : 50;
  const topShortRatio =
    Array.isArray(top) && top[0] ? parseFloat(top[0].shortAccount) * 100 : 50;

  return { longRatio, shortRatio, topLongRatio, topShortRatio };
}

export async function getBinanceFundingHistory(
  symbol: string
): Promise<{ rates: number[]; velocity: number; trend: "RISING" | "FALLING" | "FLAT" }> {
  const fallback = { rates: [], velocity: 0, trend: "FLAT" as const };
  const data = await fetchJSON(`${FAPI}/fundingRate?symbol=${symbol}&limit=8`);
  if (!Array.isArray(data) || data.length === 0) return fallback;

  const rates = data
    .map((x: any) => parseFloat(x.fundingRate) * 100)
    .sort((_, __) => 0); // preserve API order, newest first assumed

  const velocity = rates.length >= 3 ? rates[0] - rates[2] : 0;
  const trend: "RISING" | "FALLING" | "FLAT" =
    velocity < -0.005 ? "FALLING" : velocity > 0.005 ? "RISING" : "FLAT";

  return { rates, velocity, trend };
}

export async function getBinanceOrderbook(
  symbol: string
): Promise<{ bidDepth: number; askDepth: number; imbalance: number }> {
  const fallback = { bidDepth: 0, askDepth: 0, imbalance: 1.0 };
  const data = await fetchJSON(`${FAPI}/depth?symbol=${symbol}&limit=50`);
  if (!data?.bids || !data?.asks) return fallback;

  const sumUSD = (side: [string, string][], count: number) =>
    side
      .slice(0, count)
      .reduce((acc, [price, qty]) => acc + parseFloat(price) * parseFloat(qty), 0);

  const bidDepth = sumUSD(data.bids, 20);
  const askDepth = sumUSD(data.asks, 20);
  const imbalance = bidDepth / (askDepth || 1);

  return { bidDepth, askDepth, imbalance };
}

export async function getBinanceTakerFlow(
  symbol: string
): Promise<{ buyRatio: number; sellRatio: number }> {
  const fallback = { buyRatio: 50, sellRatio: 50 };
  const data = await fetchJSON(`${FAPI}/aggTrades?symbol=${symbol}&limit=100`);
  if (!Array.isArray(data) || data.length === 0) return fallback;

  let buyVol = 0;
  let sellVol = 0;
  for (const trade of data) {
    const qty = parseFloat(trade.q);
    if (trade.m === false) {
      buyVol += qty;
    } else {
      sellVol += qty;
    }
  }

  const total = buyVol + sellVol || 1;
  return {
    buyRatio: (buyVol / total) * 100,
    sellRatio: (sellVol / total) * 100,
  };
}

export async function getBinanceKlines(
  symbol: string
): Promise<number[][]> {
  const data = await fetchJSON(
    `${FAPI}/klines?symbol=${symbol}&interval=1h&limit=16`
  );
  if (!Array.isArray(data)) return [];
  return data as number[][];
}
