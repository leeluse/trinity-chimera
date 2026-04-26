import { create } from 'zustand';
import { MetricKey } from '@/types';

interface DashboardState {
  currentMetric: MetricKey;
  activeBot: string;
  chartActiveBot: string;
  logActiveBot: string;
  
  setCurrentMetric: (metric: MetricKey) => void;
  setActiveBot: (id: string) => void;
  setChartActiveBot: (id: string) => void;
  setLogActiveBot: (id: string) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  currentMetric: 'equity',
  activeBot: 'ALL',
  chartActiveBot: 'ALL',
  logActiveBot: 'ALL',

  setCurrentMetric: (metric) => set({ currentMetric: metric }),
  setActiveBot: (id) => set({ activeBot: id }),
  setChartActiveBot: (id) => set({ chartActiveBot: id }),
  setLogActiveBot: (id) => set({ logActiveBot: id }),
}));
