import { useQuery } from '@tanstack/react-query';
import client from '../../../api/client';

export interface DimensionListItem {
  id: number;
  dimension_name: string;
  entity_name: string | null;
  data_type: string;
  cardinality: number | null;
  is_primary: boolean;
  description: string | null;
}

export const getDimensions = async (): Promise<DimensionListItem[]> => {
  const res = await client.get('/api/dimensions');
  return res.data;
};

export const useDimensions = () => {
  return useQuery({
    queryKey: ['dimensions', 'list'],
    queryFn: getDimensions,
  });
};

