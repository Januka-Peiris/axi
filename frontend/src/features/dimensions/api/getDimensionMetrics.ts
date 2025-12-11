import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface LinkedMetric {
  id: number;
  name: string;
  type: string;
  description: string | null;
}

export const getDimensionMetrics = async (dimensionId: string): Promise<LinkedMetric[]> => {
  const res = await client.get(`/api/dimensions/${dimensionId}/metrics`);
  return res.data;
};

export const useDimensionMetrics = (dimensionId: string | undefined) => {
  return useQuery({
    queryKey: ['dimensions', 'metrics', dimensionId],
    queryFn: () => getDimensionMetrics(dimensionId!),
    enabled: !!dimensionId,
  });
};

