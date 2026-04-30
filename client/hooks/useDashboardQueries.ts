import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BackendAPI, fetchBotTrades, fetchBots } from "@/api";
import { MetricKey } from "@/types";

interface DashboardQueryOptions {
  statsIntervalMs?: number;
  logsIntervalMs?: number;
}

interface TimeseriesQueryOptions {
  refetchIntervalMs?: number;
  enabled?: boolean;
}

export const useDashboardQueries = (options: DashboardQueryOptions = {}) => {
  const queryClient = useQueryClient();
  const {
    statsIntervalMs = 6000,
    logsIntervalMs = 8000,
  } = options;

  // 1. Dashboard Core Stats (Metrics, Progress, Automation)
  // 1. System Automation Status (Optional - if still needed for bots, but currently disabled in backend)
  const automationQuery = useQuery({
    queryKey: ["dashboard", "automation"],
    queryFn: () => BackendAPI.getAutomationStatus().catch(() => ({ enabled: false, status: 'disabled' })),
    refetchInterval: statsIntervalMs,
  });



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

  // 4. Mutations
  const toggleAutomationMutation = useMutation({
    mutationFn: (enabled: boolean) => BackendAPI.setAutomationStatus(enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
  });

  return {
    isLoading: automationQuery.isLoading || botTradesQuery.isLoading || botsQuery.isLoading,
    botTrades: botTradesQuery.data || [],
    bots: botsQuery.data || [],
    automationStatus: automationQuery.data,
    toggleAutomation: toggleAutomationMutation.mutate,
  };
};


