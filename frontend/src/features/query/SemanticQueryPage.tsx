import React, { useState, useEffect } from 'react';
import { Terminal } from 'lucide-react';
import {
  MetricSelector,
  DimensionSelector,
  SelectionSummary,
  FilterBuilder,
  SqlPreview,
  QueryResultTable,
} from './components';
import { useSemanticQuery, useSqlOnly, type FilterItem } from './api/runSemanticQuery';

export const SemanticQueryPage: React.FC = () => {
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [filters, setFilters] = useState<FilterItem[]>([]);
  const [sql, setSql] = useState<string | null>(null);
  const [sqlLoading, setSqlLoading] = useState(false);

  const { mutate: runQuery, data: queryResult, isPending: queryLoading, error: queryError } = useSemanticQuery();
  const { mutate: generateSql, isPending: sqlOnlyLoading } = useSqlOnly();

  // Auto-generate SQL when metrics/dimensions change
  useEffect(() => {
    if (selectedMetrics.length > 0) {
      setSqlLoading(true);
      generateSql(
        {
          metrics: selectedMetrics,
          dimensions: selectedDimensions,
          filters,
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
  }, [selectedMetrics, selectedDimensions, filters]);

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
        metrics: selectedMetrics,
        dimensions: selectedDimensions,
        filters,
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
    runQuery({
      metrics: selectedMetrics,
      dimensions: selectedDimensions,
      filters,
    });
  };

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col bg-[#0d0f15] -m-6">
      {/* Header */}
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center gap-3 mb-2">
          <Terminal className="w-6 h-6 text-cyan-400" />
          <h1 className="text-2xl font-black text-white">Semantic Query Console</h1>
        </div>
        <p className="text-slate-400 text-sm">
          Build queries using metrics and dimensions from your semantic layer
        </p>
      </div>

      {/* Selection Summary */}
      <div className="p-6 border-b border-white/10">
        <SelectionSummary
          metrics={selectedMetrics}
          dimensions={selectedDimensions}
          onRemoveMetric={handleRemoveMetric}
          onRemoveDimension={handleRemoveDimension}
        />
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
            availableDimensions={selectedDimensions}
            onAdd={handleAddFilter}
            onRemove={handleRemoveFilter}
            onUpdate={handleUpdateFilter}
          />

          {/* Buttons */}
          <div className="flex gap-3">
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
          </div>

          {/* SQL Preview */}
          <SqlPreview sql={sql} isLoading={sqlLoading || sqlOnlyLoading} />

          {/* Error Display */}
          {queryError && (
            <div className="p-4 rounded-lg border border-red-500/20 bg-red-500/10">
              {(() => {
                const errorData = (queryError as any)?.response?.data;
                if (errorData?.detail) {
                  const detail = errorData.detail;
                  if (typeof detail === 'object' && detail.code) {
                    // Structured error
                    if (detail.code === 'INCOMPATIBLE_GRAIN') {
                      return (
                        <div>
                          <div className="font-semibold text-red-400 mb-2">
                            Incompatible Grain Error
                          </div>
                          <div className="text-red-300 text-sm mb-2">{detail.message}</div>
                          {detail.grains && (
                            <div className="mt-2 text-xs text-red-400">
                              <div className="font-semibold mb-1">Grain Details:</div>
                              {Object.entries(detail.grains).map(([metric, grain]: [string, any]) => (
                                <div key={metric} className="ml-2">
                                  <span className="font-mono">{metric}</span>: [{Array.isArray(grain) ? grain.join(', ') : grain}]
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    } else if (detail.code === 'INVALID_DIMENSION') {
                      return (
                        <div>
                          <div className="font-semibold text-red-400 mb-2">
                            Invalid Dimension Error
                          </div>
                          <div className="text-red-300 text-sm">
                            {detail.message}
                            {detail.allowed_dimensions && (
                              <div className="mt-2 text-xs">
                                Allowed dimensions: {detail.allowed_dimensions.join(', ')}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    }
                  }
                  return <div className="text-red-300">{typeof detail === 'string' ? detail : detail.message || 'Query failed'}</div>;
                }
                return <div className="text-red-300">Query failed: {queryError instanceof Error ? queryError.message : 'Unknown error'}</div>;
              })()}
            </div>
          )}

          {/* Result Table */}
          <QueryResultTable
            columns={queryResult?.columns || []}
            rows={queryResult?.rows || []}
            isLoading={queryLoading}
            error={queryResult?.error || null}
          />
        </div>
      </div>
    </div>
  );
};

