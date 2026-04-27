const BASE_URL = "https://api.bybit.com/v5/market";

let _scanSignal: AbortSignal | null = null;
export function setScanSignal(signal: AbortSignal | null) {
  _scanSignal = signal;
}

async function fetchJSON(url: string): Promise<any> {
  if (_scanSignal?.aborted) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  _scanSignal?.addEventListener("abort", () => controller.abort(), { once: true });

  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    clearTimeout(timer);
    return null;
  }
}

// 1. 거래 중인 USDT 선물 심볼 목록
export async function getBybitSymbols(): Promise<string[]> {
  const data = await fetchJSON(
    `${BASE_URL}/instruments-info?category=linear`
  );
  if (!data?.result?.list) return [];
  return data.result.list
    .filter(
      (item: any) =>
        item.quoteCoin === "USDT" && item.status === "Trading"
    )
    .map((item: any) => item.symbol as string);
}

// 2. 단일 심볼 티커
export async function getBybitTicker(
  symbol: string
): Promise<Record<string, string> | null> {
  const data = await fetchJSON(
    `${BASE_URL}/tickers?category=linear&symbol=${symbol}`
  );
  return data?.result?.list?.[0] ?? null;
}

// 3. 미결제약정 + 1h / 4h / 24h 변화율
export async function getBybitOI(symbol: string): Promise<{
  current: number;
  change1h: number;
  change4h: number;
  change24h: number;
}> {
  const ZERO = { current: 0, change1h: 0, change4h: 0, change24h: 0 };
  const data = await fetchJSON(
    `${BASE_URL}/open-interest?category=linear&symbol=${symbol}&intervalTime=1h&limit=25`
  );
  const list: any[] | undefined = data?.result?.list;
  if (!list || list.length < 2) return ZERO;

  const toNum = (x: any) => parseFloat(x?.openInterest ?? "0");
  const pct = (latest: number, past: number) =>
    past === 0 ? 0 : ((latest - past) / past) * 100;

  const latest = toNum(list[0]);
  const past1h = toNum(list[1]);
  const past4h = toNum(list[4]);
  const past24h = toNum(list[list.length - 1]);

  return {
    current: latest,
    change1h: pct(latest, past1h),
    change4h: list.length > 4 ? pct(latest, past4h) : 0,
    change24h: pct(latest, past24h),
  };
}

// 4. 롱/숏 비율
export async function getBybitLSRatio(symbol: string): Promise<{
  longRatio: number;
  shortRatio: number;
}> {
  const data = await fetchJSON(
    `${BASE_URL}/account-ratio?category=linear&symbol=${symbol}&period=5min&limit=1`
  );
  const item = data?.result?.list?.[0];
  if (!item) return { longRatio: 50, shortRatio: 50 };
  return {
    longRatio: parseFloat(item.buyRatio) * 100,
    shortRatio: parseFloat(item.sellRatio) * 100,
  };
}

// 5. 펀딩비 히스토리 + 추세
export async function getBybitFundingHistory(symbol: string): Promise<{
  rates: number[];
  velocity: number;
  trend: "RISING" | "FALLING" | "FLAT";
}> {
  const FALLBACK = { rates: [], velocity: 0, trend: "FLAT" as const };
  const data = await fetchJSON(
    `${BASE_URL}/funding/history?category=linear&symbol=${symbol}&limit=8`
  );
  const list: any[] | undefined = data?.result?.list;
  if (!list) return FALLBACK;

  const rates = list.map((x: any) => parseFloat(x.fundingRate) * 100);
  const velocity = rates.length >= 3 ? rates[0] - rates[2] : 0;
  const trend: "RISING" | "FALLING" | "FLAT" =
    velocity < -0.005 ? "FALLING" : velocity > 0.005 ? "RISING" : "FLAT";

  return { rates, velocity, trend };
}

// 6. 오더북 호가 깊이 & 불균형
export async function getBybitOrderbook(symbol: string): Promise<{
  bidDepth: number;
  askDepth: number;
  imbalance: number;
}> {
  const FALLBACK = { bidDepth: 0, askDepth: 0, imbalance: 1.0 };
  const data = await fetchJSON(
    `${BASE_URL}/orderbook?category=linear&symbol=${symbol}&limit=50`
  );
  const result = data?.result;
  if (!result) return FALLBACK;

  const sumDepth = (levels: string[][], count: number) =>
    levels
      .slice(0, count)
      .reduce((acc, [price, qty]) => acc + parseFloat(price) * parseFloat(qty), 0);

  const bidDepth = sumDepth(result.b ?? [], 20);
  const askDepth = sumDepth(result.a ?? [], 20);
  const imbalance = askDepth === 0 ? 1.0 : bidDepth / askDepth;

  return { bidDepth, askDepth, imbalance };
}

// 7. 테이커 매수/매도 비율
export async function getBybitTakerFlow(symbol: string): Promise<{
  buyRatio: number;
  sellRatio: number;
}> {
  const data = await fetchJSON(
    `${BASE_URL}/recent-trade?category=linear&symbol=${symbol}&limit=100`
  );
  const list: any[] | undefined = data?.result?.list;
  if (!list || list.length === 0) return { buyRatio: 50, sellRatio: 50 };

  let buyVol = 0;
  let sellVol = 0;
  for (const trade of list) {
    const size = parseFloat(trade.size ?? "0");
    if (trade.side === "Buy") buyVol += size;
    else sellVol += size;
  }
  const total = buyVol + sellVol;
  if (total === 0) return { buyRatio: 50, sellRatio: 50 };

  return {
    buyRatio: (buyVol / total) * 100,
    sellRatio: (sellVol / total) * 100,
  };
}

// 8. 시간봉 캔들 (최근 16개)
export async function getBybitKlines(symbol: string): Promise<string[][]> {
  const data = await fetchJSON(
    `${BASE_URL}/kline?category=linear&symbol=${symbol}&interval=60&limit=16`
  );
  return data?.result?.list ?? [];
}
