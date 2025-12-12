import React, { useState, useEffect } from 'react';
import { Terminal } from 'lucide-react';
import {
  MetricSelector,
  DimensionSelector,
  SelectionSummary,
  FilterBuilder,
  SqlPreview,
  QueryResultTable,
  SemanticErrorAlert,
} from './components';
import { useSemanticQuery, useSqlOnly, type FilterItem } from './api/runSemanticQuery';
import { api } from '../../api/client';
import { listSavedQueries, saveSavedQuery, runSavedQuery, getSavedQuery, type SavedQuery } from './api/savedQueries';
import { X } from 'lucide-react';
import { useDimensionsForQuery } from './api/listDimensions';

export const SemanticQueryPage: React.FC = () => {
  const [entities, setEntities] = useState<string[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [filters, setFilters] = useState<FilterItem[]>([]);
  const [limit, setLimit] = useState<number | undefined>(undefined);
  const [sql, setSql] = useState<string | null>(null);
  const [sqlLoading, setSqlLoading] = useState(false);
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([]);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveForm, setSaveForm] = useState<{ id: string; name: string; description: string; tags: string }>({ id: '', name: '', description: '', tags: '' });
  const [linkedSavedId, setLinkedSavedId] = useState<string | null>(null);
  const [savedError, setSavedError] = useState<string | null>(null);
  const [savedRunResult, setSavedRunResult] = useState<any | null>(null);
  const { groupedDimensions } = useDimensionsForQuery();

  const { mutate: runQuery, data: queryResult, isPending: queryLoading, error: queryError } = useSemanticQuery();
  const { mutate: generateSql, isPending: sqlOnlyLoading } = useSqlOnly();

  useEffect(() => {
    api.get('/api/entities')
      .then(res => {
        const names = Array.isArray(res.data) ? res.data.map((e: any) => e.name).filter(Boolean) : [];
        setEntities(names);
      })
      .catch(() => {});

    listSavedQueries().then(setSavedQueries).catch(() => {});

    // hydrate from saved query handoff
    const pending = localStorage.getItem('axi_load_saved_query');
    if (pending) {
      try {
        const parsed: SavedQuery = JSON.parse(pending);
        applySavedQuery(parsed);
      } catch {
        // ignore
      }
      localStorage.removeItem('axi_load_saved_query');
    }
  }, []);

  // Auto-generate SQL when metrics/dimensions change
  useEffect(() => {
    if (selectedMetrics.length > 0) {
      setSqlLoading(true);
      generateSql(
        {
          entity: selectedEntity,
          metrics: selectedMetrics,
          dimensions: selectedDimensions,
          filters,
          limit,
        },
        {
          onSuccess: (data) => {
            setSql(data.sql);
            setSqlLoading(false);
          },
          onError: () => {
            setSqlLoading(false);
          },
        }
      );
    } else {
      setSql(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMetrics, selectedDimensions, filters, limit, selectedEntity]);

  const handleToggleMetric = (metricName: string) => {
    setSelectedMetrics((prev) =>
      prev.includes(metricName)
        ? prev.filter((m) => m !== metricName)
        : [...prev, metricName]
    );
  };

  const handleToggleDimension = (dimensionName: string) => {
    setSelectedDimensions((prev) =>
      prev.includes(dimensionName)
        ? prev.filter((d) => d !== dimensionName)
        : [...prev, dimensionName]
    );
  };

  const handleRemoveMetric = (metric: string) => {
    setSelectedMetrics((prev) => prev.filter((m) => m !== metric));
  };

  const handleRemoveDimension = (dimension: string) => {
    setSelectedDimensions((prev) => prev.filter((d) => d !== dimension));
  };

  const handleAddFilter = () => {
    setFilters((prev) => [
      ...prev,
      { dimension: '', op: '=', value: '' },
    ]);
  };

  const handleRemoveFilter = (index: number) => {
    setFilters((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpdateFilter = (index: number, filter: FilterItem) => {
    setFilters((prev) => prev.map((f, i) => (i === index ? filter : f)));
  };

  const handleGenerateSql = () => {
    if (selectedMetrics.length === 0) return;
    setSqlLoading(true);
    generateSql(
      {
        entity: selectedEntity,
        metrics: selectedMetrics,
        dimensions: selectedDimensions,
        filters,
        limit,
      },
      {
        onSuccess: (data) => {
          setSql(data.sql);
          setSqlLoading(false);
        },
        onError: () => {
          setSqlLoading(false);
        },
      }
    );
  };

  const handleRunQuery = () => {
    if (selectedMetrics.length === 0) return;
    setSavedRunResult(null);
    runQuery(
      {
        entity: selectedEntity,
        metrics: selectedMetrics,
        dimensions: selectedDimensions,
        filters,
        limit,
      },
      {
        onSuccess: (data) => {
          // Save to recent queries with SQL from the result
          const recent = {
            entity: selectedEntity,
            metrics: selectedMetrics,
            dimensions: selectedDimensions,
            filters,
            sql: data.sql || sql,
            limit,
            ts: Date.now(),
          };
          const prev = JSON.parse(localStorage.getItem('axi_recent_queries') || '[]');
          const next = [recent, ...prev].slice(0, 5);
          localStorage.setItem('axi_recent_queries', JSON.stringify(next));
        },
      }
    );
  };

  const applySavedQuery = (q: SavedQuery) => {
    if (!q) return;
    setSelectedEntity(q.entity || '');
    setSelectedMetrics(q.metrics || []);
    setSelectedDimensions(q.dimensions || []);
    setFilters((q.filters as any) || []);
    setLimit(q.limit);
    setLinkedSavedId(q.id);
    setSaveForm({
      id: q.id,
      name: q.name || q.id,
      description: q.description || '',
      tags: (q.tags || []).join(','),
    });
  };

  const slugify = (val: string) => val.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'saved_query';

  const handleSaveQuery = async () => {
    setSavedError(null);
    const payload: SavedQuery = {
      id: saveForm.id || slugify(saveForm.name || selectedMetrics[0] || 'saved_query'),
      name: saveForm.name || selectedMetrics.join(', '),
      description: saveForm.description || undefined,
      entity: selectedEntity,
      metrics: selectedMetrics,
      dimensions: selectedDimensions,
      filters,
      limit,
      tags: saveForm.tags ? saveForm.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
    };
    if (!payload.metrics.length) {
      setSavedError('Select at least one metric before saving.');
      return;
    }
    try {
      const saved = await saveSavedQuery(payload);
      setSavedQueries(prev => {
        const others = prev.filter(q => q.id !== saved.id);
        return [...others, saved];
      });
      setLinkedSavedId(saved.id);
      setSaveModalOpen(false);
    } catch (err: any) {
      setSavedError(err?.response?.data?.detail?.message || err?.message || 'Failed to save query');
    }
  };

  const handleLoadSaved = async (id: string) => {
    setSavedError(null);
    try {
      const full = await getSavedQuery(id);
      applySavedQuery(full);
    } catch (err: any) {
      setSavedError(err?.response?.data?.detail?.message || err?.message || 'Failed to load saved query');
    }
  };

  const handleRunSaved = async (id: string) => {
    setSavedError(null);
    try {
      const res = await runSavedQuery(id, {
        override_filters: filters,
        override_limit: limit,
      });
      setSavedRunResult(res);
      setSql(res.sql);
    } catch (err: any) {
      setSavedError(err?.response?.data?.detail?.message || err?.message || 'Run failed');
    }
  };

  const filterDimensionOptions = selectedEntity
    ? Object.entries(groupedDimensions)
        .filter(([ent]) => ent === selectedEntity)
        .flatMap(([, dims]) => dims.map((d) => d.name))
    : Object.entries(groupedDimensions)
        .flatMap(([, dims]) => dims.map((d) => d.name));

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col bg-[#0d0f15] -m-6">
      {/* Header / Context Bar */}
      <div className="p-6 border-b border-white/10 flex flex-col gap-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Terminal className="w-6 h-6 text-cyan-400" />
            <div>
              <h1 className="text-2xl font-black text-white">Semantic Query Console</h1>
              <p className="text-slate-400 text-sm">Build queries with metrics, dimensions, and filters—no SQL needed.</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="px-2 py-1 rounded border border-white/10 bg-white/5">
              {selectedMetrics.length} metric{selectedMetrics.length === 1 ? '' : 's'}
            </span>
            <span className="px-2 py-1 rounded border border-white/10 bg-white/5">
              {selectedDimensions.length} dimension{selectedDimensions.length === 1 ? '' : 's'}
            </span>
            {linkedSavedId && (
              <span className="px-2 py-1 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
                Linked to {linkedSavedId}
              </span>
            )}
          </div>
        </div>
          <div className="flex items-center gap-3 flex-wrap">
            <label className="text-sm text-slate-300">Entity</label>
          <select
            value={selectedEntity}
            onChange={(e) => {
              setSelectedEntity(e.target.value);
              setSelectedMetrics([]);
              setSelectedDimensions([]);
            }}
            className="bg-[#151821] border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
          >
            <option value="">All entities</option>
            {entities.map((ent) => (
              <option key={ent} value={ent}>{ent}</option>
            ))}
          </select>
            <SelectionSummary
              metrics={selectedMetrics}
              dimensions={selectedDimensions}
              onRemoveMetric={handleRemoveMetric}
              onRemoveDimension={handleRemoveDimension}
            />
          </div>
        </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Metric & Dimension Picker */}
        <div className="w-80 border-r border-white/10 bg-[#151821] flex flex-col">
          <div className="p-4 border-b border-white/10">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
              Metrics
            </h2>
          </div>
          <div className="flex-1 overflow-hidden">
            <MetricSelector
              selectedMetrics={selectedMetrics}
              onToggle={handleToggleMetric}
              entityFilter={selectedEntity}
            />
          </div>
          <div className="p-4 border-t border-white/10">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
              Dimensions
            </h2>
          </div>
          <div className="flex-1 overflow-hidden">
            <DimensionSelector
              selectedDimensions={selectedDimensions}
              selectedMetrics={selectedMetrics}
              entity={selectedEntity}
              onToggle={handleToggleDimension}
            />
          </div>
        </div>

        {/* Right Panel - Query Builder */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Selected Metrics */}
          {selectedMetrics.length > 0 && (
            <div>
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">
                Selected Metrics
              </h3>
              <div className="flex flex-wrap gap-2">
                {selectedMetrics.map((metric) => (
                  <span
                    key={metric}
                    className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-sm"
                  >
                    {metric}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Selected Dimensions */}
          {selectedDimensions.length > 0 && (
            <div>
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">
                Selected Dimensions
              </h3>
              <div className="flex flex-wrap gap-2">
                {selectedDimensions.map((dimension) => (
                  <span
                    key={dimension}
                    className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 text-sm"
                  >
                    {dimension}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Filters */}
          <FilterBuilder
            filters={filters}
            availableDimensions={filterDimensionOptions}
            onAdd={handleAddFilter}
            onRemove={handleRemoveFilter}
            onUpdate={handleUpdateFilter}
          />

          {/* Limit + Buttons */}
          <div className="flex flex-wrap gap-3 items-center">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              Limit
              <input
                type="number"
                value={limit ?? ''}
                onChange={(e) => setLimit(e.target.value ? Number(e.target.value) : undefined)}
                placeholder="500"
                className="w-24 bg-[#151821] border border-white/10 rounded px-2 py-1 text-white text-sm"
              />
            </label>
            <button
              onClick={handleGenerateSql}
              disabled={selectedMetrics.length === 0 || sqlLoading}
              className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg border border-cyan-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Generate SQL
            </button>
            <button
              onClick={handleRunQuery}
              disabled={selectedMetrics.length === 0 || queryLoading}
              className="px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {queryLoading ? 'Running...' : 'Run Query'}
            </button>
            <button
              onClick={() => {
                setSaveModalOpen(true);
                setSaveForm({
                  id: linkedSavedId || slugify(selectedMetrics[0] || selectedEntity || 'saved_query'),
                  name: saveForm.name || selectedMetrics.join(', ') || selectedEntity || 'Saved Query',
                  description: saveForm.description,
                  tags: saveForm.tags,
                });
              }}
              className="px-4 py-2 bg-white/5 hover:bg-white/10 text-white rounded-lg border border-white/10 transition-colors"
            >
              Save Query
            </button>
          </div>

          {/* Saved Queries quick list */}
          <div className="rounded-lg border border-white/10 bg-[#111827] p-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-white">Saved Queries</div>
              {linkedSavedId && (
                <span className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-1 rounded">
                  Linked: {linkedSavedId}
                </span>
              )}
            </div>
            <div className="mt-2 grid md:grid-cols-2 gap-2 max-h-40 overflow-auto">
              {savedQueries.length === 0 ? (
                <div className="text-sm text-slate-500">No saved queries yet.</div>
              ) : (
                savedQueries.map((q) => (
                  <div key={q.id} className="flex items-center justify-between bg-white/5 rounded px-2 py-1">
                    <div>
                      <div className="text-sm text-white">{q.name}</div>
                      <div className="text-xs text-slate-400">{q.id}</div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleLoadSaved(q.id)}
                        className="text-xs text-cyan-400 hover:text-white"
                      >
                        Load
                      </button>
                      <button
                        onClick={() => handleRunSaved(q.id)}
                        className="text-xs text-emerald-400 hover:text-white"
                      >
                        Run
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
            {savedError && <div className="text-xs text-red-400 mt-2">{savedError}</div>}
          </div>

          <SemanticErrorAlert error={(queryError as any)?.response?.data?.detail || (queryResult as any)?.error} />

          {/* Status + SQL Preview */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-slate-400">
              {queryResult?.rows?.length ? `${queryResult.rows.length} rows` : 'No rows yet'}{" "}
              {queryResult?.execution_ms ? `• ${queryResult.execution_ms} ms` : ''}{" "}
              {limit ? `• limit ${limit}` : ''}
            </div>
          </div>
          <SqlPreview sql={sql} isLoading={sqlLoading || sqlOnlyLoading} />

          {/* Result Table */}
          <QueryResultTable
            columns={(savedRunResult?.columns as any) || queryResult?.columns || []}
            rows={(savedRunResult?.rows as any) || queryResult?.rows || []}
            isLoading={queryLoading}
            error={savedRunResult?.error || queryResult?.error || null}
          />
        </div>
      </div>

      {saveModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#0f172a] border border-white/10 rounded-xl w-full max-w-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-bold text-white">Save Query</div>
                <div className="text-sm text-slate-400">Persist this query as YAML for reuse.</div>
              </div>
              <button onClick={() => setSaveModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3">
              <label className="block text-sm text-slate-300">
                ID
                <input
                  value={saveForm.id}
                  onChange={(e) => setSaveForm({ ...saveForm, id: e.target.value })}
                  className="w-full bg-[#151821] border border-white/10 rounded px-3 py-2 text-sm text-white mt-1"
                  placeholder="monthly_revenue_uk"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Name
                <input
                  value={saveForm.name}
                  onChange={(e) => setSaveForm({ ...saveForm, name: e.target.value })}
                  className="w-full bg-[#151821] border border-white/10 rounded px-3 py-2 text-sm text-white mt-1"
                  placeholder="Monthly Revenue (UK)"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Description
                <textarea
                  value={saveForm.description}
                  onChange={(e) => setSaveForm({ ...saveForm, description: e.target.value })}
                  className="w-full bg-[#151821] border border-white/10 rounded px-3 py-2 text-sm text-white mt-1"
                  placeholder="Total revenue per month for UK customers"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Tags (comma separated)
                <input
                  value={saveForm.tags}
                  onChange={(e) => setSaveForm({ ...saveForm, tags: e.target.value })}
                  className="w-full bg-[#151821] border border-white/10 rounded px-3 py-2 text-sm text-white mt-1"
                  placeholder="finance, exec_dashboard"
                />
              </label>
              {savedError && <div className="text-sm text-red-400">{savedError}</div>}
            </div>
            <div className="flex justify-end gap-3">
              <button onClick={() => setSaveModalOpen(false)} className="px-4 py-2 text-slate-300">Cancel</button>
              <button
                onClick={handleSaveQuery}
                className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg border border-cyan-500/20"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
