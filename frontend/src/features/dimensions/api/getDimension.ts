import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface DimensionDetail {
  id: number;
  name: string;
  entity_name: string | null;
  data_type: string;
  cardinality: number | null;
  is_primary: boolean;
  description: string | null;
}

export const getDimension = async (id: string): Promise<DimensionDetail> => {
  const res = await client.get(`/api/dimensions/${id}`);
  return res.data;
};

export const useDimension = (id: string | undefined) => {
  return useQuery({
    queryKey: ['dimensions', 'detail', id],
    queryFn: () => getDimension(id!),
    enabled: !!id,
  });
};

