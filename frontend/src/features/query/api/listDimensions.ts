import { useDimensions } from '../../dimensions/api/getDimensions';

export interface DimensionOption {
  id: number;
  name: string;
  entity_name: string | null;
  data_type: string;
}

export const useDimensionsForQuery = () => {
  const { data: dimensions, isLoading, error } = useDimensions();
  
  // Group dimensions by entity
  const groupedDimensions = dimensions?.reduce((acc, dim) => {
    const entity = dim.entity_name || 'Uncategorized';
    if (!acc[entity]) {
      acc[entity] = [];
    }
    acc[entity].push({
      id: dim.id,
      name: dim.dimension_name,
      entity_name: dim.entity_name,
      data_type: dim.data_type,
    });
    return acc;
  }, {} as Record<string, DimensionOption[]>) || {};

  return {
    dimensions: dimensions || [],
    groupedDimensions,
    isLoading,
    error,
  };
};
