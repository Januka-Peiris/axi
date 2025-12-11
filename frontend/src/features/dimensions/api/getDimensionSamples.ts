import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface DimensionSample {
  value: string;
}

export const getDimensionSamples = async (dimensionId: string): Promise<DimensionSample[]> => {
  const res = await client.get(`/api/dimensions/${dimensionId}/sample`);
  const data = res.data;
  // Handle both array of strings and array of objects
  if (Array.isArray(data)) {
    return data.map((item) =>
      typeof item === 'string' ? { value: item } : item
    );
  }
  return [];
};

export const useDimensionSamples = (dimensionId: string | undefined, enabled: boolean = false) => {
  return useQuery({
    queryKey: ['dimensions', 'samples', dimensionId],
    queryFn: () => getDimensionSamples(dimensionId!),
    enabled: !!dimensionId && enabled,
  });
};

