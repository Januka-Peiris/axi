import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../../api/client';

export const useDeleteMetric = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (metricName: string) => {
      const response = await api.delete(`/api/metrics/${metricName}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics'] });
    },
  });
};

