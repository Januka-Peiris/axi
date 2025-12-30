import React, { useState, useEffect, useMemo, useDeferredValue } from 'react';
import { Plus, X, Save, AlertCircle, Link2, Loader2 } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../../api/client';

interface MetricBuilderProps {
  onClose: () => void;
  onSuccess?: () => void;
  isOpen?: boolean;
  initialData?: {
    metric: string;
    description?: string;
    entity?: string;
    expression?: string;
    type?: string;
    grain?: string[];
    dimensions?: string[];
    tags?: string[];
  };
}

interface Entity {
  name: string;
  model?: string;
}

interface VisibleDimension {
  name: string;
  entity: string;
  model?: string;
  hops: number;
  via: string[];
  via_description?: string;
  relationship_type: 'direct' | 'explicit' | 'inferred';
  join_keys: any[];
  grain_relation: string;
}

export const MetricBuilder: React.FC<MetricBuilderProps> = ({ onClose, onSuccess, isOpen = true, initialData }) => {
  const [metricName, setMetricName] = useState(initialData?.metric || '');
  const [description, setDescription] = useState(initialData?.description || '');
  const [entity, setEntity] = useState(initialData?.entity || '');
  const [expression, setExpression] = useState(initialData?.expression || '');
  const [type, setType] = useState(initialData?.type || '');
  const [grain, setGrain] = useState<string[]>(initialData?.grain || []);
  const [dimensions, setDimensions] = useState<string[]>(initialData?.dimensions || []);
  const [tags, setTags] = useState<string[]>(initialData?.tags || []);
  const [newTag, setNewTag] = useState('');
  const [newGrainDim, setNewGrainDim] = useState('');
  const [newDimension, setNewDimension] = useState('');
  const [availableEntities, setAvailableEntities] = useState<Entity[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  const queryClient = useQueryClient();
  const isEdit = !!initialData?.metric;

  // Load entities
  useEffect(() => {
    api.get('/api/entities')
      .then(res => {
        setAvailableEntities(res.data || []);
      })
      .catch(err => {
        console.error('Failed to load entities:', err);
      });
  }, []);

  // Load joinable dimensions using reachability API
  const { data: contextData, isLoading: contextLoading } = useQuery({
    queryKey: ['metric-context', entity],
    queryFn: async () => {
      if (!entity) return null;
      const res = await api.post('/api/query/sqlrunner/context', {
        metrics: [],
        entities: [entity],
        dimensions: []
      });
      return res.data;
    },
    enabled: !!entity
  });

  // Split dimensions into direct and joinable
  const directDimensions = useMemo(() =>
    (contextData?.visible_dimensions || []).filter((d: VisibleDimension) => d.hops === 0),
    [contextData]
  );

  const joinableDimensions = useMemo(() =>
    (contextData?.visible_dimensions || []).filter((d: VisibleDimension) => d.hops > 0),
    [contextData]
  );

  const allDimensions = useMemo(() =>
    (contextData?.visible_dimensions || []) as VisibleDimension[],
    [contextData]
  );

  // Debounce inputs to reduce API calls (improves performance and reduces server load)
  const deferredExpression = useDeferredValue(expression);
  const deferredDimensions = useDeferredValue(dimensions);
  const deferredGrain = useDeferredValue(grain);

  // Load join plan preview with error handling and loading states
  const {
    data: joinPlan,
    isLoading: joinPlanLoading,
    error: joinPlanError
  } = useQuery({
    queryKey: ['join-plan', entity, deferredExpression, deferredDimensions, deferredGrain],
    queryFn: async () => {
      if (!entity) return null;
      if (!deferredExpression && deferredDimensions.length === 0 && deferredGrain.length === 0) return null;

      const res = await api.post('/api/metrics/preview-join-plan', {
        entity,
        expression: deferredExpression || '',
        dimensions: [...new Set([...deferredDimensions, ...deferredGrain])] // Combine and dedupe
      });
      return res.data;
    },
    enabled: !!entity && (!!deferredExpression || deferredDimensions.length > 0 || deferredGrain.length > 0),
    retry: 1, // Only retry once to avoid excessive API calls
    staleTime: 1000 // Cache for 1 second to reduce redundant calls
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post('/api/metrics', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics'] });
      onSuccess?.();
      onClose();
    },
    onError: (error: any) => {
      const errorData = error.response?.data;
      if (errorData?.detail) {
        if (typeof errorData.detail === 'object' && errorData.detail.errors) {
          // Structured errors object
          const errorList = Array.isArray(errorData.detail.errors) 
            ? errorData.detail.errors 
            : [errorData.detail.errors];
          setErrors(errorList);
        } else if (typeof errorData.detail === 'string') {
          setErrors([errorData.detail]);
        } else {
          setErrors([JSON.stringify(errorData.detail)]);
        }
      } else {
        setErrors([error.message || 'Failed to create metric']);
      }
    }
  });

  const updateMutation = useMutation({
    mutationFn: (data: any) => api.put(`/api/metrics/${initialData?.metric}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics'] });
      onSuccess?.();
      onClose();
    },
    onError: (error: any) => {
      const errorData = error.response?.data;
      if (errorData?.detail) {
        if (typeof errorData.detail === 'object' && errorData.detail.errors) {
          // Structured errors object
          const errorList = Array.isArray(errorData.detail.errors) 
            ? errorData.detail.errors 
            : [errorData.detail.errors];
          setErrors(errorList);
        } else if (typeof errorData.detail === 'string') {
          setErrors([errorData.detail]);
        } else {
          setErrors([JSON.stringify(errorData.detail)]);
        }
      } else {
        setErrors([error.message || 'Failed to update metric']);
      }
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors([]);

    const data = {
      metric: metricName,
      description,
      entity,
      expression,
      type: type || undefined,
      grain: grain.length > 0 ? grain : undefined,
      dimensions: dimensions.length > 0 ? dimensions : undefined,
      tags: tags.length > 0 ? tags : undefined,
    };

    if (isEdit) {
      updateMutation.mutate(data);
    } else {
      createMutation.mutate(data);
    }
  };

  const addTag = () => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      setTags([...tags, newTag.trim()]);
      setNewTag('');
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter(t => t !== tag));
  };

  const addGrainDim = () => {
    if (newGrainDim.trim() && !grain.includes(newGrainDim.trim())) {
      setGrain([...grain, newGrainDim.trim()]);
      setNewGrainDim('');
    }
  };

  const removeGrainDim = (dim: string) => {
    setGrain(grain.filter(d => d !== dim));
  };

  const addDimension = () => {
    if (newDimension.trim() && !dimensions.includes(newDimension.trim())) {
      setDimensions([...dimensions, newDimension.trim()]);
      setNewDimension('');
    }
  };

  const removeDimension = (dim: string) => {
    setDimensions(dimensions.filter(d => d !== dim));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-panel border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold">
              {isEdit ? 'Edit Metric' : 'Create Metric'}
            </h2>
            <button
              onClick={onClose}
              className="text-text-secondary hover:text-text-primary"
            >
              <X size={20} />
            </button>
          </div>

          {errors.length > 0 && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <div className="flex items-center gap-2 text-red-400 mb-2">
                <AlertCircle size={16} />
                <span className="font-semibold">Validation Errors</span>
              </div>
              <ul className="list-disc list-inside text-sm text-red-300 space-y-1">
                {errors.map((error, idx) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Metric Name *</label>
              <input
                type="text"
                value={metricName}
                onChange={(e) => setMetricName(e.target.value)}
                disabled={isEdit}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg"
                required
                placeholder="total_revenue"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-white placeholder:text-slate-500 resize-none"
                rows={3}
                placeholder="Total revenue across all orders"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Entity *</label>
              <select
                value={entity}
                onChange={(e) => setEntity(e.target.value)}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg"
                required
              >
                <option value="">Select entity...</option>
                {availableEntities.map(ent => (
                  <option key={ent.name} value={ent.name}>{ent.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Expression *</label>
              <input
                type="text"
                value={expression}
                onChange={(e) => setExpression(e.target.value)}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg font-mono text-sm"
                required
                placeholder="SUM(amount) or {other_metric} / {total}"
              />
              <p className="text-xs text-text-secondary mt-1">
                Must contain exactly one aggregation (SUM, COUNT, AVG, MIN, MAX) or reference other metrics using {"{metric_name}"}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Type *</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-white"
                required
              >
                <option value="">Select aggregation type...</option>
                <option value="sum">Sum</option>
                <option value="count">Count</option>
                <option value="avg">Average</option>
                <option value="min">Min</option>
                <option value="max">Max</option>
                <option value="custom">Custom</option>
              </select>
              <p className="text-xs text-text-secondary mt-1">
                Select the aggregation type for this metric
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Grain (Optional)</label>
              <div className="flex gap-2 mb-2">
                <select
                  value={newGrainDim}
                  onChange={(e) => setNewGrainDim(e.target.value)}
                  className="flex-1 px-3 py-2 bg-background border border-border rounded-lg"
                  disabled={contextLoading}
                >
                  <option value="">{contextLoading ? 'Loading dimensions...' : 'Select dimension...'}</option>
                  {directDimensions.length > 0 && (
                    <optgroup label="Direct">
                      {directDimensions.map((dim: VisibleDimension) => (
                        <option key={dim.name} value={dim.name}>{dim.name}</option>
                      ))}
                    </optgroup>
                  )}
                  {joinableDimensions.length > 0 && (
                    <optgroup label="Joinable (requires JOIN)">
                      {joinableDimensions.map((dim: VisibleDimension) => (
                        <option key={dim.name} value={dim.name}>
                          {dim.name} ({dim.hops} hop{dim.hops > 1 ? 's' : ''} via {dim.entity})
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
                <button
                  type="button"
                  onClick={addGrainDim}
                  className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg border border-cyan-500/20"
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {grain.map(dim => (
                  <span
                    key={dim}
                    className="px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/20 flex items-center gap-1"
                  >
                    {dim}
                    <button
                      type="button"
                      onClick={() => removeGrainDim(dim)}
                      className="hover:text-red-400"
                    >
                      <X size={14} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Allowed Dimensions</label>
              <div className="flex gap-2 mb-2">
                <select
                  value={newDimension}
                  onChange={(e) => setNewDimension(e.target.value)}
                  className="flex-1 px-3 py-2 bg-background border border-border rounded-lg"
                  disabled={contextLoading}
                >
                  <option value="">{contextLoading ? 'Loading dimensions...' : 'Select dimension...'}</option>
                  {directDimensions.length > 0 && (
                    <optgroup label="Direct">
                      {directDimensions.map((dim: VisibleDimension) => (
                        <option key={dim.name} value={dim.name}>{dim.name}</option>
                      ))}
                    </optgroup>
                  )}
                  {joinableDimensions.length > 0 && (
                    <optgroup label="Joinable (requires JOIN)">
                      {joinableDimensions.map((dim: VisibleDimension) => (
                        <option key={dim.name} value={dim.name}>
                          {dim.name} ({dim.hops} hop{dim.hops > 1 ? 's' : ''} via {dim.entity})
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
                <button
                  type="button"
                  onClick={addDimension}
                  className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg border border-cyan-500/20"
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {dimensions.map(dim => (
                  <span
                    key={dim}
                    className="px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/20 flex items-center gap-1"
                  >
                    {dim}
                    <button
                      type="button"
                      onClick={() => removeDimension(dim)}
                      className="hover:text-red-400"
                    >
                      <X size={14} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Tags</label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                  className="flex-1 px-3 py-2 bg-background border border-border rounded-lg"
                  placeholder="finance"
                />
                <button
                  type="button"
                  onClick={addTag}
                  className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg border border-cyan-500/20"
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {tags.map(tag => (
                  <span
                    key={tag}
                    className="px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/20 flex items-center gap-1"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="hover:text-red-400"
                    >
                      <X size={14} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Join Plan Preview - Loading State */}
            {joinPlanLoading && entity && (deferredExpression || deferredDimensions.length > 0 || deferredGrain.length > 0) && (
              <div className="mt-4 p-3 bg-slate-500/5 border border-slate-500/20 rounded-lg">
                <div className="flex items-center gap-2 text-slate-400 text-xs">
                  <Loader2 size={14} className="animate-spin" />
                  Analyzing required joins...
                </div>
              </div>
            )}

            {/* Join Plan Preview - Error State */}
            {joinPlanError && !joinPlanLoading && (
              <div className="mt-4 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-lg">
                <div className="flex items-center gap-2 text-yellow-400 text-xs">
                  <AlertCircle size={14} />
                  <span>Unable to preview joins. You can still save the metric.</span>
                </div>
              </div>
            )}

            {/* Join Plan Preview - Success State */}
            {joinPlan && joinPlan.join_paths && Object.keys(joinPlan.join_paths).length > 0 && !joinPlanLoading && (
              <div className="mt-4 p-3 bg-cyan-500/5 border border-cyan-500/20 rounded-lg">
                <div className="flex items-center gap-2 text-cyan-400 text-sm font-medium mb-2">
                  <Link2 size={16} />
                  Automatic JOINs Required
                </div>
                <div className="text-xs text-slate-300 space-y-1">
                  {Object.entries(joinPlan.join_paths).map(([entity, path]: [string, any]) => (
                    <div key={entity} className="flex items-start gap-2">
                      <span className="text-slate-500">→</span>
                      <span>
                        <span className="text-slate-400">{joinPlan.base_entity}</span>
                        {' → '}
                        <span className="text-cyan-400">{entity}</span>
                        <span className="text-slate-500 ml-2">
                          ({path.length} hop{path.length > 1 ? 's' : ''})
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
                {joinPlan.metric_references && joinPlan.metric_references.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-cyan-500/10">
                    <div className="text-xs text-slate-400">
                      References metrics: {joinPlan.metric_references.map((ref: string) => `{${ref}}`).join(', ')}
                    </div>
                  </div>
                )}
                {joinPlan.warnings && joinPlan.warnings.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-yellow-500/20">
                    <div className="flex items-center gap-1 text-yellow-400 text-xs">
                      <AlertCircle size={12} />
                      <span>Warnings:</span>
                    </div>
                    <div className="text-xs text-yellow-300/80 mt-1 space-y-1">
                      {joinPlan.warnings.map((warning: string, idx: number) => (
                        <div key={idx}>• {warning}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-3 pt-4">
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="flex-1 px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Save size={16} />
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : (isEdit ? 'Update' : 'Create')}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-background hover:bg-panel border border-border rounded-lg"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
