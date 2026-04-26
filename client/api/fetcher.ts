// Base fetcher with bypass logic for localtunnel/ngrok

const normalizeApiBase = (value: string): string => value.replace(/\/+$/, "").replace(/\/api$/, "");
const IS_PRODUCTION = process.env.NODE_ENV === "production";

// Use explicit public backend URL first (Vercel), then fallback to Next.js rewrite (/api).
const rawPublicApiBase = (process.env.NEXT_PUBLIC_API_URL || "").trim();
const DEFAULT_TUNNEL_SUBDOMAIN = (process.env.NEXT_PUBLIC_TUNNEL_SUBDOMAIN || "lsy-super-trend").trim();
const DEFAULT_TUNNEL_HOST = (process.env.NEXT_PUBLIC_TUNNEL_HOST || "https://loca.lt").trim();
const normalizedTunnelHost = DEFAULT_TUNNEL_HOST.replace(/\/+$/, "").replace(/^http:\/\//, "https://");
const tunnelHostNoScheme = normalizedTunnelHost.replace(/^https?:\/\//, "");
const DEFAULT_TUNNEL_BASE =
  DEFAULT_TUNNEL_SUBDOMAIN && tunnelHostNoScheme
    ? normalizeApiBase(`https://${DEFAULT_TUNNEL_SUBDOMAIN}.${tunnelHostNoScheme}`)
    : "";

// In production, if no explicit API URL is provided, default to the tunnel base to ensure connectivity.
export const API_BASE = rawPublicApiBase 
  ? normalizeApiBase(rawPublicApiBase) 
  : (IS_PRODUCTION ? DEFAULT_TUNNEL_BASE : "");

export const API_BASE_URL = '/api';
const RAW_FETCH_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_FETCH_TIMEOUT_MS || "30000");
const FETCH_TIMEOUT_MS = Number.isFinite(RAW_FETCH_TIMEOUT_MS)
  ? (RAW_FETCH_TIMEOUT_MS <= 0 ? 0 : Math.max(3000, RAW_FETCH_TIMEOUT_MS))
  : 30000;
const LOCAL_API_FALLBACKS = [
  "http://localhost:8000",
  "http://127.0.0.1:8000",
  "http://localhost:8765",
].map(normalizeApiBase);

const withBypassHeaders = (options: RequestInit): RequestInit => ({
  ...options,
  headers: {
    ...options.headers,
    "ngrok-skip-browser-warning": "true",
    "Bypass-Tunnel-Reminder": "true",
  },
});

type FetchWithBypassOptions = RequestInit & {
  timeoutMs?: number;
};

const resolveTimeoutMs = (timeoutMs?: number): number | null => {
  if (!Number.isFinite(timeoutMs)) {
    return FETCH_TIMEOUT_MS <= 0 ? null : FETCH_TIMEOUT_MS;
  }
  const parsed = Number(timeoutMs);
  if (parsed <= 0) {
    return null;
  }
  return Math.max(3000, parsed);
};

const buildCandidates = (url: string): string[] => {
  if (url.startsWith("http")) return [url];
  const path = url.startsWith("/") ? url : `/${url}`;
  const candidates: string[] = [];
  const isHttpsPage =
    typeof window !== "undefined" && window.location?.protocol === "https:";
  const configuredRemote =
    !!API_BASE && !API_BASE.includes("localhost") && !API_BASE.includes("127.0.0.1");

  if (configuredRemote) {
    candidates.push(`${API_BASE}${path}`);
    candidates.push(path);
  } else {
    candidates.push(path);
    if (API_BASE) candidates.push(`${API_BASE}${path}`);
  }

  if (!IS_PRODUCTION) {
    for (const localBase of LOCAL_API_FALLBACKS) {
      if (isHttpsPage && localBase.startsWith("http://")) continue;
      candidates.push(`${localBase}${path}`);
    }
  }

  if (isHttpsPage && !configuredRemote && DEFAULT_TUNNEL_BASE) {
    candidates.push(`${DEFAULT_TUNNEL_BASE}${path}`);
  }

  return [...new Set(candidates)];
};

const shouldRetryFallback = (candidate: string, response: Response): boolean => {
  const isRewriteCandidate = candidate.startsWith("/");
  if (isRewriteCandidate) {
    const vercelProxyError = response.headers.get("x-vercel-error");
    if (response.status === 404 || response.status >= 500 || !!vercelProxyError) return true;
  }

  const isConfiguredRemote =
    !!API_BASE &&
    candidate.startsWith(API_BASE) &&
    !API_BASE.includes("localhost") &&
    !API_BASE.includes("127.0.0.1");

  if (!isConfiguredRemote) return false;

  const tunnelUnavailable = response.headers.get("x-localtunnel-status") === "Tunnel Unavailable";
  const vercelProxyError = response.headers.get("x-vercel-error");
  const retryableStatus = response.status === 404 || response.status >= 500;
  const contentType = response.headers.get("content-type") || "";
  const htmlResponse = contentType.includes("text/html");

  return tunnelUnavailable || retryableStatus || htmlResponse || !!vercelProxyError;
};

export const fetchWithBypass = async (url: string, options: FetchWithBypassOptions = {}) => {
  const { timeoutMs, ...requestInit } = options;
  const effectiveTimeoutMs = resolveTimeoutMs(timeoutMs);
  const candidates = buildCandidates(url);

  let lastError: unknown = null;

  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i];
    const isLast = i === candidates.length - 1;
    const timeoutController = new AbortController();
    let abortReason: "timeout" | "aborted" | null = null;
    const timeoutId = effectiveTimeoutMs === null
      ? null
      : setTimeout(() => {
          abortReason = "timeout";
          timeoutController.abort("timeout");
        }, effectiveTimeoutMs);
    const externalSignal = requestInit.signal;
    let externalAbortListener: (() => void) | null = null;

    if (externalSignal) {
      externalAbortListener = () => {
        abortReason = "aborted";
        timeoutController.abort("aborted");
      };
      if (externalSignal.aborted) {
        if (timeoutId !== null) {
          clearTimeout(timeoutId);
        }
        throw new DOMException("Request aborted", "AbortError");
      }
      externalSignal.addEventListener("abort", externalAbortListener, { once: true });
    }

    const method = String(requestInit.method || "GET").toUpperCase();
    const requestOptions = withBypassHeaders({
      ...requestInit,
      cache: method === "GET" ? "no-store" : requestInit.cache,
      signal: timeoutController.signal,
    });

    try {
      const response = await fetch(candidate, requestOptions);
      if (!isLast && shouldRetryFallback(candidate, response)) {
        console.warn(`[API] Candidate failed, retrying: ${candidate} (Status: ${response.status})`);
        continue;
      }
      return response;
    } catch (error) {
      const normalizedError =
        error instanceof DOMException && error.name === "AbortError" && abortReason === "timeout"
          ? new Error("Request timed out")
          : error;
      lastError = normalizedError;
      console.warn(`[API] Candidate error: ${candidate}`, normalizedError);
      if (isLast) throw normalizedError;
    } finally {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
      if (externalSignal && externalAbortListener) {
        externalSignal.removeEventListener("abort", externalAbortListener);
      }
    }
  }

  throw (lastError as Error) || new Error("Failed to fetch");
};

// Generic JSON fetcher with optional retries
export async function fetchJson(url: string, options: FetchWithBypassOptions = {}, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetchWithBypass(url, options);
      if (response.status === 429) {
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
        continue;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (e) {
      if (attempt === retries) throw e;
      await new Promise(r => setTimeout(r, 300 * (attempt + 1)));
    }
  }
}
