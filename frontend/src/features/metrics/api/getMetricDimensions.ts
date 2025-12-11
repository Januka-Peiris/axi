import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface LinkedDimension {
  id: number;
  name: string;
  type: string;
  cardinality: number | null;
  description: string | null;
}

export const getMetricDimensions = async (metricId: string): Promise<LinkedDimension[]> => {
  const res = await client.get(`/api/metrics/${metricId}/dimensions`);
  return res.data;
};

export const useMetricDimensions = (metricId: string | undefined) => {
  return useQuery({
    queryKey: ['metrics', 'dimensions', metricId],
    queryFn: () => getMetricDimensions(metricId!),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};

