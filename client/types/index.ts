export type MetricKey = 'score' | 'return' | 'sharpe' | 'mdd' | 'win';

export interface PerformanceRow {
  name: string;
  color: string;
  ret: string;
  sh: string;
  mdd: string;
  pos: boolean;
}
