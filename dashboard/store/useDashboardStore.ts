/**
 * Dashboard Store (Zustand)
 * 전역 상태 관리: 포트폴리오, 에이전트, 거래, Arbiter 결정 등
 */

import { create } from 'zustand';
import type {
  PortfolioState,
  AgentMetrics,
  Trade,
  ArbiterDecision,
  BattleStep,
  WebSocketEvent,
  MarketAnalysis,
  GeneratedStrategy,
  LLMArbiterAnalysis,
} from '../types';

interface DashboardState {
  // Core data
  portfolio: PortfolioState | null;
  agents: Record<string, AgentMetrics>;
  trades: Trade[];
  decisions: ArbiterDecision[];
  battleHistory: BattleStep[];

  // Phase 3 data
  marketAnalysis: MarketAnalysis | null;
  generatedStrategies: GeneratedStrategy[];
  llmAnalysis: LLMArbiterAnalysis | null;

  // Connection state
  isConnected: boolean;
  lastUpdate: string | null;
  latency: number;
}

interface DashboardActions {
  // Actions
  setPortfolio: (state: PortfolioState) => void;
  setAgents: (agents: Record<string, AgentMetrics>) => void;
  updateAgent: (name: string, metrics: Partial<AgentMetrics>) => void;
  addTrade: (trade: Trade) => void;
  addDecision: (decision: ArbiterDecision) => void;
  addBattleStep: (step: BattleStep) => void;

  // Phase 3 actions
  setMarketAnalysis: (analysis: MarketAnalysis) => void;
  addGeneratedStrategy: (strategy: GeneratedStrategy) => void;
  setLLMAnalysis: (analysis: LLMArbiterAnalysis) => void;

  // Connection state
  setConnectionState: (connected: boolean) => void;
  setLatency: (latency: number) => void;
  setLastUpdate: (timestamp: string) => void;

  // WebSocket event handler
  handleWebSocketEvent: (event: WebSocketEvent) => void;

  // Reset
  reset: () => void;
}

const initialState: DashboardState = {
  portfolio: null,
  agents: {},
  trades: [],
  decisions: [],
  battleHistory: [],
  marketAnalysis: null,
  generatedStrategies: [],
  llmAnalysis: null,
  isConnected: false,
  lastUpdate: null,
  latency: 0,
} as DashboardState;

export const useDashboardStore = create<DashboardState & DashboardActions>((set, get) => ({
  ...initialState,

  // 포트폴리오 상태 설정
  setPortfolio: (portfolio) =>
    set((state) => ({
      portfolio,
      agents: portfolio.agent_metrics || state.agents,
      lastUpdate: portfolio.timestamp || new Date().toISOString(),
    })),

  // 전체 에이전트 설정
  setAgents: (agents) =>
    set({
      agents,
    }),

  // 개별 에이전트 업데이트
  updateAgent: (name, metrics) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [name]: {
          ...state.agents[name],
          ...metrics,
        } as AgentMetrics,
      },
    })),

  // 거래 추가
  addTrade: (trade) =>
    set((state) => ({
      trades: [trade, ...state.trades].slice(0, 1000), // 최대 1000개 유지
      lastUpdate: new Date().toISOString(),
    })),

  // Arbiter 결정 추가
  addDecision: (decision) =>
    set((state) => ({
      decisions: [decision, ...state.decisions].slice(0, 100), // 최대 100개 유지
      lastUpdate: decision.timestamp,
    })),

  // 배틀 스텝 추가
  addBattleStep: (step) =>
    set((state) => ({
      battleHistory: [step, ...state.battleHistory].slice(0, 500), // 최대 500개 유지
    })),

  // 연결 상태 설정
  setConnectionState: (isConnected) =>
    set({
      isConnected,
    }),

  // 지연 시간 설정
  setLatency: (latency) =>
    set({
      latency,
    }),

  // 마지막 업데이트 시간 설정
  setLastUpdate: (lastUpdate) =>
    set({
      lastUpdate,
    }),

  // WebSocket 이벤트 처리
  handleWebSocketEvent: (event) => {
    switch (event.type) {
      case 'portfolio':
        get().setPortfolio(event.data as PortfolioState);
        break;
      case 'agent_update':
        const agentMetrics = event.data as AgentMetrics;
        get().updateAgent(agentMetrics.name, agentMetrics);
        break;
      case 'new_trade':
        get().addTrade(event.data as Trade);
        break;
      case 'arbiter_decision':
        get().addDecision(event.data as ArbiterDecision);
        break;
      case 'battle_step':
        get().addBattleStep(event.data as BattleStep);
        break;
    }
  },

  // Phase 3 액션들
  setMarketAnalysis: (marketAnalysis) =>
    set({
      marketAnalysis,
      lastUpdate: new Date().toISOString(),
    }),

  addGeneratedStrategy: (strategy) =>
    set((state) => ({
      generatedStrategies: [strategy, ...state.generatedStrategies].slice(0, 50),
      lastUpdate: new Date().toISOString(),
    })),

  setLLMAnalysis: (llmAnalysis) =>
    set({
      llmAnalysis,
      lastUpdate: new Date().toISOString(),
    }),

  // 상태 초기화
  reset: () => set(initialState),
}));

// 선택기 함수들
export const selectPortfolio = (state: DashboardState) => state.portfolio;
export const selectAgents = (state: DashboardState) => state.agents;
export const selectTrades = (state: DashboardState) => state.trades;
export const selectDecisions = (state: DashboardState) => state.decisions;
export const selectIsConnected = (state: DashboardState) => state.isConnected;
export const selectLatency = (state: DashboardState) => state.latency;
export const selectLastUpdate = (state: DashboardState) => state.lastUpdate;

export default useDashboardStore;
