import { useMetrics } from '../../metrics/api/getMetrics';

export interface MetricOption {
  id: number;
  name: string;
  entity_name: string | null;
  type: string;
}

export const useMetricsForQuery = () => {
  const { data: metrics, isLoading, error } = useMetrics();
  
  // Group metrics by entity
  const groupedMetrics = metrics?.reduce((acc, metric) => {
    const entity = metric.entity_name || 'Uncategorized';
    if (!acc[entity]) {
      acc[entity] = [];
    }
    acc[entity].push({
      id: metric.id,
      name: metric.name,
      entity_name: metric.entity_name,
      type: metric.type,
    });
    return acc;
  }, {} as Record<string, MetricOption[]>) || {};

  return {
    metrics: metrics || [],
    groupedMetrics,
    isLoading,
    error,
  };
};
