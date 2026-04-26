import { fetchJson } from "./fetcher";

const BINANCE_BASE = "https://api.binance.com";
const BINANCE_FUTURES_BASE = "https://fapi.binance.com";

export class MarketAPI {
  /**
   * Fetch Klines from Binance Spot
   */
  static async getKlines(symbol: string = "BTCUSDT", interval: string = "15m", limit: number = 96) {
    const url = `${BINANCE_BASE}/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;
    return fetchJson(url);
  }

  /**
   * Fetch Klines from Binance Futures
   */
  static async getFuturesKlines(symbol: string, interval: string, limit: number) {
    const url = `${BINANCE_FUTURES_BASE}/fapi/v1/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`;
    return fetchJson(url);
  }

  /**
   * Fetch tickers from Binance Futures
   */
  static async getFuturesTickers() {
    const url = `${BINANCE_FUTURES_BASE}/fapi/v1/ticker/24hr`;
    return fetchJson(url);
  }

  /**
   * Fetch open interest from Binance Futures
   */
  static async getOpenInterest(symbol: string) {
    const url = `${BINANCE_FUTURES_BASE}/fapi/v1/openInterest?symbol=${symbol}`;
    return fetchJson(url);
  }
}
