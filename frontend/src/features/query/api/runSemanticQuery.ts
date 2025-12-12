import { useMutation } from '@tanstack/react-query';
import client from '../../../api/client';

export interface FilterItem {
  dimension: string;
  op: '=' | '!=' | '>' | '<' | '>=' | '<=' | 'IN' | 'NOT IN' | 'BETWEEN' | 'LIKE';
  value: any;
}

export interface SemanticQueryRequest {
  entity?: string;
  metrics: string[];
  dimensions: string[];
  filters: FilterItem[];
  limit?: number;
}

export interface SemanticQueryResponse {
  sql: string;
  columns: string[];
  rows: any[];
  generated_at: string;
  error: string | null;
  execution_ms?: number;
}

export const runSemanticQuery = async (req: SemanticQueryRequest): Promise<SemanticQueryResponse> => {
  const res = await client.post('/api/query/semantic', req);
  return res.data;
};

export const useSemanticQuery = () => {
  return useMutation({
    mutationFn: runSemanticQuery,
  });
};

export const generateSqlOnly = async (req: SemanticQueryRequest): Promise<{ sql: string; generated_at: string }> => {
  const res = await client.post('/api/query/semantic/sql-only', req);
  return res.data;
};

export const useSqlOnly = () => {
  return useMutation({
    mutationFn: generateSqlOnly,
  });
};
