import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface CompiledSqlResponse {
  sql: string;
  metric_name: string;
  version: string;
  warehouse: string;
}

export const getMetricCompiledSql = async (
  metricId: string,
  warehouse: string = 'snowflake'
): Promise<CompiledSqlResponse> => {
  const res = await client.get(`/api/metrics/${metricId}/compiled-sql`, {
    params: { warehouse },
  });
  return res.data;
};

export const useMetricCompiledSql = (
  metricId: string | undefined,
  warehouse: string = 'snowflake'
) => {
  return useQuery({
    queryKey: ['metrics', 'compiled-sql', metricId, warehouse],
    queryFn: () => getMetricCompiledSql(metricId!, warehouse),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};
