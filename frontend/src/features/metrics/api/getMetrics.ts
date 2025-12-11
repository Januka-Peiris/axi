import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface MetricListItem {
  id: number;
  name: string;
  entity_name: string | null;
  type: string;
  expression: string;
  default_dimensions: string[] | null | undefined;
  description: string | null;
}

export const getMetrics = async (): Promise<MetricListItem[]> => {
  const res = await client.get('/api/metrics');
  // Normalize default_dimensions to always be an array
  return res.data.map((metric: any) => ({
    ...metric,
    default_dimensions: Array.isArray(metric.default_dimensions) 
      ? metric.default_dimensions 
      : [],
  }));
};

export const useMetrics = () => {
  return useQuery({
    queryKey: ['metrics', 'list'],
    queryFn: getMetrics,
  });
};

