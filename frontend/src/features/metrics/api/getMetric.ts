import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export type MetricStatus = 'active' | 'deprecated' | 'disabled';

export interface MetricDetail {
  id: number;
  name: string;
  entity: string | null;
  entity_name?: string | null;
  type: string;
  expression: string;
  default_dimensions: string[] | null | undefined;
  description: string | null;
  tags: string[] | null | undefined;
  source_model: string | null;
  grain: string | string[] | null;
  created_at: string | null;
  updated_at: string | null;
  version?: string;
  status?: MetricStatus;
  deprecation_date?: string | null;
  replacement_metric?: string | null;
}

export const getMetric = async (id: string): Promise<MetricDetail> => {
  const res = await client.get(`/api/metrics/${id}`);
  // Normalize array fields to always be arrays
  return {
    ...res.data,
    default_dimensions: Array.isArray(res.data.default_dimensions) 
      ? res.data.default_dimensions 
      : [],
    tags: Array.isArray(res.data.tags) 
      ? res.data.tags 
      : [],
  };
};

export const useMetric = (id: string | undefined) => {
  return useQuery({
    queryKey: ['metrics', 'detail', id],
    queryFn: () => getMetric(id!),
    enabled: !!id && id !== 'null' && id !== 'undefined',
  });
};

