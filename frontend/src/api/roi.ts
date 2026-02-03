import { useQuery } from '@tanstack/react-query';
import client from './client';

export interface RoiSummaryResponse {
  top_metrics: Array<{ metric_name: string; usage_count: number; deprecated_access_count: number }>;
  total_matched_queries: number;
  total_deprecated_access: number;
  deprecated_last_7_days: number;
  deprecated_previous_7_days: number;
  estimated_analyst_hours_saved: number;
  hours_saved_per_query: number;
}

export const getRoiSummary = async (topN: number = 20): Promise<RoiSummaryResponse> => {
  const res = await client.get('/api/roi/summary', { params: { top_n: topN } });
  return res.data;
};

export const useRoiSummary = (topN: number = 20) => {
  return useQuery({
    queryKey: ['roi', 'summary', topN],
    queryFn: () => getRoiSummary(topN),
  });
};
