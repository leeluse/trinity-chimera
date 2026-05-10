import { useQuery } from "@tanstack/react-query";
import { fetchBotTrades, fetchBots } from "@/api";

interface DashboardQueryOptions {
  statsIntervalMs?: number;
  logsIntervalMs?: number;
}

export const useDashboardQueries = (options: DashboardQueryOptions = {}) => {
  const {
    statsIntervalMs = 6000,
    logsIntervalMs = 8000,
  } = options;

  // 4. Bot Trades Logs
  const botTradesQuery = useQuery({
    queryKey: ["dashboard", "botTrades"],
    queryFn: () => fetchBotTrades(50),
    enabled: true, // Always fetch for now
    refetchInterval: logsIntervalMs,
    refetchIntervalInBackground: false,
  });

  // 5. Bot List (for metrics/chart)
  const botsQuery = useQuery({
    queryKey: ["dashboard", "bots"],
    queryFn: () => fetchBots(),
    enabled: true,
    refetchInterval: statsIntervalMs,
    refetchIntervalInBackground: false,
  });

  return {
    isLoading: botTradesQuery.isLoading || botsQuery.isLoading,
    botTrades: botTradesQuery.data || [],
    bots: botsQuery.data || [],
  };
};

