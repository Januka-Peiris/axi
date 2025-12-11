import { useMutation } from '@tanstack/react-query';
import client from '../../../api/client';

export interface SemanticQueryRequest {
  metrics: string[];
  dimensions: string[];
  filters: string[];
}

export interface SemanticQueryResponse {
  sql: string;
  preview: any[];
}

export const runSemanticQuery = async (req: SemanticQueryRequest): Promise<SemanticQueryResponse> => {
  const res = await client.post('/api/metrics/query/semantic', req);
  return res.data;
};

export const useSemanticQuery = () => {
  return useMutation({
    mutationFn: runSemanticQuery,
  });
};

