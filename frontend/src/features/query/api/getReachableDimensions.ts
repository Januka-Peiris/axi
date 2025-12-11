import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';
import type { SemanticQueryRequest } from './runSemanticQuery';

export const getReachableDimensions = async (metrics: string[]): Promise<string[]> => {
  if (metrics.length === 0) {
    return [];
  }
  
  const res = await client.post('/api/query/semantic/reachable-dimensions', {
    metrics,
    dimensions: [],
    filters: [],
  } as SemanticQueryRequest);
  
  return res.data.dimensions || [];
};

export const useReachableDimensions = (metrics: string[]) => {
  return useQuery({
    queryKey: ['reachable-dimensions', metrics.sort().join(',')],
    queryFn: () => getReachableDimensions(metrics),
    enabled: metrics.length > 0,
  });
};

