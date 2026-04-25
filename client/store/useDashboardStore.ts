import { create } from 'zustand';
import { MetricKey } from '@/types';

interface DashboardState {
  currentMetric: MetricKey;
  activeAgent: string;
  chartActiveAgent: string;
  logActiveAgent: string;
  
  setCurrentMetric: (metric: MetricKey) => void;
  setActiveAgent: (id: string) => void;
  setChartActiveAgent: (id: string) => void;
  setLogActiveAgent: (id: string) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  currentMetric: 'equity',
  activeAgent: 'ALL',
  chartActiveAgent: 'ALL',
  logActiveAgent: 'ALL',

  setCurrentMetric: (metric) => set({ currentMetric: metric }),
  setActiveAgent: (id) => set({ activeAgent: id }),
  setChartActiveAgent: (id) => set({ chartActiveAgent: id }),
  setLogActiveAgent: (id) => set({ logActiveAgent: id }),
}));
