export type MetricKey = 'equity' | 'return' | 'sharpe' | 'mdd' | 'win';

export interface PerformanceRow {
  agentId?: string;
  name: string;
  color: string;
  ret: string;
  sh: string;
  mdd: string;
  pos: boolean;
}
