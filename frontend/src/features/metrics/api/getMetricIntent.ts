import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface SemanticIntentResponse {
  metric_name: string;
  metric_version: string;
  base_entity: string;
  grain: string[];
  measures: Array<{ name: string; column_ref: string; aggregation: string }>;
  dimensions: string[];
  time_dimension?: { name: string; column_ref: string; granularity?: string } | null;
  filters: unknown[];
  join_path: Array<{
    from_entity: string;
    to_entity: string;
    from_column: string;
    to_column: string;
    join_type: string;
  }>;
}

export const getMetricIntent = async (metricId: string): Promise<SemanticIntentResponse> => {
  const res = await client.get(`/api/metrics/${metricId}/intent`);
  return res.data;
};

export const useMetricIntent = (metricId: string | undefined) => {
  return useQuery({
    queryKey: ['metrics', 'intent', metricId],
    queryFn: () => getMetricIntent(metricId!),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};
