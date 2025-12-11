import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface LinkedEntity {
  id: number;
  name: string;
}

export const getDimensionEntities = async (dimensionId: string): Promise<LinkedEntity[]> => {
  const res = await client.get(`/api/dimensions/${dimensionId}/entities`);
  return res.data;
};

export const useDimensionEntities = (dimensionId: string | undefined) => {
  return useQuery({
    queryKey: ['dimensions', 'entities', dimensionId],
    queryFn: () => getDimensionEntities(dimensionId!),
    enabled: !!dimensionId,
  });
};

