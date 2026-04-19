import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { APIClient, DashboardMetrics, DashboardProgress, EvolutionLogEvent, DecisionLogEvent } from "@/lib/api";
import { MetricKey } from "@/types";

export const useDashboardQueries = () => {
  const queryClient = useQueryClient();

  // 1. Dashboard Core Stats (Metrics, Progress, Automation)
  const statsQuery = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: async () => {
      const [prog, met, auto] = await Promise.all([
        APIClient.getDashboardProgress(),
        APIClient.getDashboardMetrics(),
        APIClient.getAutomationStatus()
      ]);
      return { prog, met, auto };
    },
    refetchInterval: 4000,
  });

  // 2. Evolution Logs
  const evolutionLogsQuery = useQuery({
    queryKey: ["dashboard", "evolutionLogs"],
    queryFn: () => APIClient.getEvolutionLog(220),
    refetchInterval: 4000,
  });

  // 3. Decision/Backtest Logs
  const decisionLogsQuery = useQuery({
    queryKey: ["dashboard", "decisionLogs"],
    queryFn: () => APIClient.getDecisionLogs(260),
    refetchInterval: 4000,
  });

  // 4. Mutations
  const toggleAutomationMutation = useMutation({
    mutationFn: (enabled: boolean) => APIClient.setAutomationStatus(enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
  });

  return {
    stats: statsQuery.data,
    isLoading: statsQuery.isLoading || evolutionLogsQuery.isLoading || decisionLogsQuery.isLoading,
    evolutionEvents: evolutionLogsQuery.data || [],
    decisionLogs: decisionLogsQuery.data || [],
    automationStatus: statsQuery.data?.auto,
    metricsData: statsQuery.data?.met,
    dashboardProgress: statsQuery.data?.prog,
    toggleAutomation: toggleAutomationMutation.mutate,
  };
};

export const useAgentTimeseries = (metric: MetricKey, agentIds: string[]) => {
  return useQuery({
    queryKey: ["dashboard", "timeseries", metric, agentIds.join("|")],
    queryFn: async () => {
      const results: Record<string, number[]> = {};
      await Promise.all(agentIds.map(async (id) => {
        try {
          results[id] = await APIClient.getAgentTimeseries(id, metric);
        } catch {
          results[id] = [];
        }
      }));
      return results;
    },
    enabled: agentIds.length > 0,
    refetchInterval: 4000,
  });
};
