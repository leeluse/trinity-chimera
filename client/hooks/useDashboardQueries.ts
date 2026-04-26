import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BackendAPI, fetchBotTrades, fetchBots } from "@/api";
import { MetricKey } from "@/types";

interface DashboardQueryOptions {
  enableEvolutionLogs?: boolean;
  enableDecisionLogs?: boolean;
  statsIntervalMs?: number;
  logsIntervalMs?: number;
  evolutionLogLimit?: number;
  decisionLogLimit?: number;
}

interface TimeseriesQueryOptions {
  refetchIntervalMs?: number;
  enabled?: boolean;
}

export const useDashboardQueries = (options: DashboardQueryOptions = {}) => {
  const queryClient = useQueryClient();
  const {
    enableEvolutionLogs = true,
    enableDecisionLogs = true,
    statsIntervalMs = 6000,
    logsIntervalMs = 8000,
    evolutionLogLimit = 120,
    decisionLogLimit = 140,
  } = options;

  // 1. Dashboard Core Stats (Metrics, Progress, Automation)
  const statsQuery = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: async () => {
      const [prog, met, auto] = await Promise.all([
        BackendAPI.getDashboardProgress(),
        BackendAPI.getDashboardMetrics(),
        BackendAPI.getAutomationStatus()
      ]);
      return { prog, met, auto };
    },
    refetchInterval: statsIntervalMs,
    refetchIntervalInBackground: false,
  });

  // 2. Evolution Logs
  const evolutionLogsQuery = useQuery({
    queryKey: ["dashboard", "evolutionLogs"],
    queryFn: () => BackendAPI.getEvolutionLog(evolutionLogLimit),
    enabled: enableEvolutionLogs,
    refetchInterval: logsIntervalMs,
    refetchIntervalInBackground: false,
  });

  // 3. Decision/Backtest Logs
  const decisionLogsQuery = useQuery({
    queryKey: ["dashboard", "decisionLogs"],
    queryFn: () => BackendAPI.getDecisionLogs(decisionLogLimit),
    enabled: enableDecisionLogs,
    refetchInterval: logsIntervalMs,
    refetchIntervalInBackground: false,
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
    stats: statsQuery.data,
    isLoading: statsQuery.isLoading || evolutionLogsQuery.isLoading || decisionLogsQuery.isLoading || botTradesQuery.isLoading,
    evolutionEvents: evolutionLogsQuery.data || [],
    decisionLogs: decisionLogsQuery.data || [],
    botTrades: botTradesQuery.data || [],
    bots: botsQuery.data || [],
    automationStatus: statsQuery.data?.auto,
    metricsData: statsQuery.data?.met,
    dashboardProgress: statsQuery.data?.prog,
    toggleAutomation: toggleAutomationMutation.mutate,
  };
};

export const useAgentTimeseries = (
  metric: MetricKey,
  agentIds: string[],
  options: TimeseriesQueryOptions = {}
) => {
  const { refetchIntervalMs = 7000, enabled = true } = options;
  return useQuery({
    queryKey: ["dashboard", "timeseries", metric, agentIds.join("|")],
    queryFn: async () => {
      const results: Record<string, number[]> = {};
      await Promise.all(agentIds.map(async (id) => {
        // [MOD] Skip UUIDs (Bots) as they don't have agent timeseries API yet
        if (id.includes("-")) {
          results[id] = [];
          return;
        }
        try {
          results[id] = await BackendAPI.getAgentTimeseries(id, metric);
        } catch {
          results[id] = [];
        }
      }));
      return results;
    },
    enabled: enabled && agentIds.length > 0,
    refetchInterval: refetchIntervalMs,
    refetchIntervalInBackground: false,
  });
};
