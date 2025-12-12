import client from '../../../api/client';

export interface SavedQueryFilter {
  dimension: string;
  op: '=' | '!=' | '>' | '<' | '>=' | '<=' | 'IN' | 'NOT IN' | 'BETWEEN' | 'LIKE';
  value: any;
}

export interface SavedQuery {
  id: string;
  name: string;
  description?: string;
  entity: string;
  metrics: string[];
  dimensions: string[];
  filters: SavedQueryFilter[];
  limit?: number;
  tags?: string[];
}

export interface RunSavedQueryRequest {
  override_filters?: SavedQueryFilter[];
  override_limit?: number;
}

export const listSavedQueries = async (): Promise<SavedQuery[]> => {
  const res = await client.get('/api/saved_queries');
  return res.data;
};

export const getSavedQuery = async (id: string): Promise<SavedQuery> => {
  const res = await client.get(`/api/saved_queries/${id}`);
  return res.data;
};

export const saveSavedQuery = async (payload: SavedQuery): Promise<SavedQuery> => {
  const res = await client.post('/api/saved_queries', payload);
  return res.data;
};

export const deleteSavedQuery = async (id: string): Promise<void> => {
  await client.delete(`/api/saved_queries/${id}`);
};

export const runSavedQuery = async (id: string, payload?: RunSavedQueryRequest) => {
  const res = await client.post(`/api/saved_queries/${id}/run`, payload || {});
  return res.data;
};
