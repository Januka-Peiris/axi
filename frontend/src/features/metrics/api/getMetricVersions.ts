import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface MetricVersionRecord {
  id: number;
  metric_name: string;
  version: string;
  definition_snapshot: Record<string, unknown>;
  status: 'active' | 'deprecated' | 'disabled';
  created_at: string;
  deprecated_at: string | null;
  replacement_metric: string | null;
}

export interface MetricVersionsResponse {
  metric_name: string;
  versions: MetricVersionRecord[];
}

export const getMetricVersions = async (metricId: string): Promise<MetricVersionsResponse> => {
  const res = await client.get(`/api/metrics/${metricId}/versions`);
  return res.data;
};

export const useMetricVersions = (metricId: string | undefined) => {
  return useQuery({
    queryKey: ['metrics', 'versions', metricId],
    queryFn: () => getMetricVersions(metricId!),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};
