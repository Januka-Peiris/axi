import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api/client';

export interface MetricSample {
  columns: string[];
  rows: any[];
}

export const getMetricSample = async (metricId: string, limit: number = 20): Promise<MetricSample> => {
  // Handle both numeric ID and metric name
  const metricParam = encodeURIComponent(metricId);
  const res = await api.get(`/api/metrics/${metricParam}/sample?limit=${limit}`);
  return res.data;
};

export const useMetricSample = (metricId: string | undefined, limit: number = 20) => {
  return useQuery({
    queryKey: ['metrics', 'sample', metricId, limit],
    queryFn: () => getMetricSample(metricId!, limit),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};

