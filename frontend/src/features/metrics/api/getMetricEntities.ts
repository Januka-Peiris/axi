import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface LinkedEntity {
  name: string;
  model: string | null;
}

export const getMetricEntities = async (metricId: string): Promise<LinkedEntity[]> => {
  const res = await client.get(`/api/metrics/${metricId}/entities`);
  return res.data;
};

export const useMetricEntities = (metricId: string | undefined) => {
  return useQuery({
    queryKey: ['metrics', 'entities', metricId],
    queryFn: () => getMetricEntities(metricId!),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};

