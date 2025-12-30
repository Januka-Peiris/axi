import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

// Relationship join key information
export type JoinKey = {
  from: string;  // e.g., "orders.customer_id"
  to: string;    // e.g., "customers.id"
  type: 'explicit' | 'inferred' | 'unknown';
};

// Visible dimension with relationship context
export type VisibleDimension = {
  name: string;
  entity: string;
  data_type: string;
  is_pk: boolean;
  is_fk: boolean;
  model?: string;
  via: string[];  // Path of hops: ["orders -> customers", "customers -> regions"]
  via_description?: string;  // Human readable: "orders → customers → regions"
  hops: number;
  relationship_type: 'explicit' | 'inferred';
  join_keys: JoinKey[];
  grain_relation: 'compatible';
};

// Excluded dimension with reason
export type ExcludedDimension = {
  name: string;
  entity?: string;
  model?: string;
  reason: 'no_relationship_path' | 'grain_incompatible' | 'metric_grain_unknown';
  dim_grain?: string[];
  metric_grain?: string[];
};

// Visible metric with compatibility info
export type VisibleMetric = {
  name: string;
  reason: 'shared_grain' | 'rollup_safe';
  model?: string;
  grain?: string[];
};

// Excluded metric with reason
export type ExcludedMetric = {
  name: string;
  reason: 'grain_incompatible' | 'grain_unknown' | 'no_relationship_path';
  model?: string;
  metric_grain?: string[];
  base_grain?: string[];
};

// Joinable entity with path info
export type JoinableEntity = {
  entity: string;
  model: string;
  via: string[];
  join_type: 'many_to_one';
  keys: JoinKey[];
};

export type SqlRunnerContextResponse = {
  visible_metrics: VisibleMetric[];
  excluded_metrics?: ExcludedMetric[];
  visible_dimensions: VisibleDimension[];
  excluded_dimensions?: ExcludedDimension[];
  joinable_entities: JoinableEntity[];
  base_metric?: string;
  base_model?: string;
  base_grain?: string[];
  error?: string;
  warning?: string;
};

const isSqlRunnerContextResponse = (data: unknown): data is SqlRunnerContextResponse => {
  if (!data || typeof data !== 'object') return false;
  const typed = data as Record<string, unknown>;
  return Array.isArray(typed.visible_metrics) && Array.isArray(typed.visible_dimensions) && Array.isArray(typed.joinable_entities);
};

const normalizeContextResponse = (data: unknown): SqlRunnerContextResponse => {
  if (isSqlRunnerContextResponse(data)) {
    return data;
  }

  return {
    visible_metrics: [],
    visible_dimensions: [],
    joinable_entities: [],
    excluded_metrics: [],
    excluded_dimensions: [],
    warning: 'Context response missing expected fields; returning empty context.',
  };
};

export const fetchSqlRunnerContext = async (metrics: string[], entities: string[] = []): Promise<SqlRunnerContextResponse> => {
  const res = await client.post<SqlRunnerContextResponse>('/api/query/sqlrunner/context', {
    metrics,
    entities,
    dimensions: [],
  });
  return normalizeContextResponse(res.data);
};

export const useSqlRunnerContext = (metrics: string[], entities: string[] = []) =>
  useQuery<SqlRunnerContextResponse>({
    queryKey: ['sqlrunner-context', metrics.sort().join(','), entities.sort().join(',')],
    queryFn: () => fetchSqlRunnerContext(metrics, entities),
    enabled: metrics.length > 0,
    staleTime: 30_000,
  });
