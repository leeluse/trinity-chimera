import { SECTORS } from "./constants";

export const getSector = (sym: string) => SECTORS[sym] || "—";

export const fmt = {
  price: (v: number | null | undefined) => {
    if (v == null) return "—";
    const n = Number(v);
    if (n >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
    if (n >= 1) return n.toFixed(3);
    if (n >= 0.01) return n.toFixed(4);
    if (n >= 0.0001) return n.toFixed(6);
    return n.toExponential(2);
  },
  pct: (v: number | null | undefined, decimals = 2) => {
    if (v == null || isNaN(v)) return "—";
    const n = Number(v);
    const s = n.toFixed(decimals);
    return (n >= 0 ? "+" : "") + s + "%";
  },
  multiplier: (v: number | null | undefined, decimals = 1) => {
    if (v == null || isNaN(v)) return "—";
    return Number(v).toFixed(decimals) + "x";
  },
  time: (date: Date) => {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  },
};

export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function fetchJson(url: string, retries = 2): Promise<unknown> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const r = await fetch(url);
      if (r.status === 429) {
        await sleep(1000 * (attempt + 1));
        continue;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      if (attempt === retries) throw e;
      await sleep(300 * (attempt + 1));
    }
  }
  return null;
}
