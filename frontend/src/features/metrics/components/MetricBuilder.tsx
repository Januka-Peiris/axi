import React, { useState, useEffect } from 'react';
import { Plus, X, Save, AlertCircle } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
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

export const MetricBuilder: React.FC<MetricBuilderProps> = ({ onClose, onSuccess, isOpen = true, initialData }) => {
  if (!isOpen) return null;
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
  const [availableDimensions, setAvailableDimensions] = useState<string[]>([]);
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

  // Load dimensions when entity changes
  useEffect(() => {
    if (entity) {
      // Get dimensions for this entity's model
      api.get('/api/dimensions')
        .then(res => {
          const entityDims = (res.data || [])
            .filter((d: any) => d.entity_name === entity)
            .map((d: any) => d.dimension_name || d.name);
          setAvailableDimensions(entityDims);
        })
        .catch(err => console.error('Failed to load dimensions:', err));
    } else {
      setAvailableDimensions([]);
    }
  }, [entity]);

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
                placeholder="SUM(amount)"
              />
              <p className="text-xs text-text-secondary mt-1">
                Must contain exactly one aggregation (SUM, COUNT, AVG, MIN, MAX)
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
                >
                  <option value="">Select dimension...</option>
                  {availableDimensions.map(dim => (
                    <option key={dim} value={dim}>{dim}</option>
                  ))}
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
                >
                  <option value="">Select dimension...</option>
                  {availableDimensions.map(dim => (
                    <option key={dim} value={dim}>{dim}</option>
                  ))}
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

