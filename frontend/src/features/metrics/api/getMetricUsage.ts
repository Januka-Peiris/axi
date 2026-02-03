import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface MetricUsageByVersion {
  version: string;
  usage_count: number;
  deprecated_access_count: number;
  first_seen: string | null;
  last_seen: string | null;
}

export interface MetricUsageResponse {
  metric_name: string;
  total_usage_count: number;
  total_deprecated_access_count: number;
  first_seen: string | null;
  last_seen: string | null;
  by_version: MetricUsageByVersion[];
}

export const getMetricUsage = async (metricId: string): Promise<MetricUsageResponse> => {
  const res = await client.get(`/api/metrics/${metricId}/usage`);
  return res.data;
};

export const useMetricUsage = (metricId: string | undefined) => {
  return useQuery({
    queryKey: ['metrics', 'usage', metricId],
    queryFn: () => getMetricUsage(metricId!),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};

export interface UsageTimeseriesPoint {
  date: string;
  usage_count: number;
  deprecated_access_count: number;
}

export interface MetricUsageTimeseriesResponse {
  metric_name: string;
  series: UsageTimeseriesPoint[];
}

export const getMetricUsageTimeseries = async (
  metricId: string,
  dateFrom?: string,
  dateTo?: string
): Promise<MetricUsageTimeseriesResponse> => {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;
  const res = await client.get(`/api/metrics/${metricId}/usage/timeseries`, { params });
  return res.data;
};

export const useMetricUsageTimeseries = (
  metricId: string | undefined,
  dateFrom?: string,
  dateTo?: string
) => {
  return useQuery({
    queryKey: ['metrics', 'usage', 'timeseries', metricId, dateFrom, dateTo],
    queryFn: () => getMetricUsageTimeseries(metricId!, dateFrom, dateTo),
    enabled: !!metricId && metricId !== 'null' && metricId !== 'undefined',
  });
};
