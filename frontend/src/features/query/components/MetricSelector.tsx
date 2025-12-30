import React, { useMemo, useState } from 'react';
import { Search, Check, AlertCircle, Layers } from 'lucide-react';
import { useMetricsForQuery } from '../api/listMetrics';
import { useSqlRunnerContext } from '../api/getSqlRunnerContext';
import type { VisibleMetric, ExcludedMetric } from '../api/getSqlRunnerContext';

interface MetricSelectorProps {
  selectedMetrics: string[];
  onToggle: (metricName: string) => void;
  entityFilter?: string;
}

// Helper to get a compatibility badge
const getCompatibilityBadge = (reason: VisibleMetric['reason']) => {
  if (reason === 'shared_grain') {
    return { label: 'Same grain', color: 'text-emerald-400 bg-emerald-500/10' };
  }
  return { label: 'Rollup safe', color: 'text-cyan-400 bg-cyan-500/10' };
};

export const MetricSelector: React.FC<MetricSelectorProps> = ({
  selectedMetrics,
  onToggle,
  entityFilter,
}) => {
  const { groupedMetrics, isLoading, error } = useMetricsForQuery();
  const contextQuery = useSqlRunnerContext(selectedMetrics, []);
  const context = contextQuery.data;
  const [search, setSearch] = useState('');
  const [showExcluded, setShowExcluded] = useState(false);

  // Build lookup for metric compatibility info
  const metricMeta = useMemo(() => {
    const map = new Map<string, VisibleMetric>();
    (context?.visible_metrics || []).forEach((m: VisibleMetric) => {
      map.set(m.name, m);
    });
    return map;
  }, [context?.visible_metrics]);

  const allowedMetrics = useMemo(() => {
    // When a metric is selected, only show compatible metrics from context; always include already-selected ones
    if (!context || selectedMetrics.length === 0) return null;
    const allowedSet = new Set<string>(selectedMetrics);
    (context.visible_metrics || []).forEach((m: VisibleMetric) => allowedSet.add(m.name));
    return allowedSet;
  }, [context, selectedMetrics]);

  const excludedMetrics = context?.excluded_metrics || [];

  const filteredGroups = useMemo(() => {
    const normalizedFilter = (entityFilter || '').toLowerCase();
    const allGroups = Object.entries(groupedMetrics);
    const sortedGroups = allGroups.sort(([a], [b]) => a.localeCompare(b));

    return sortedGroups
      .filter(([group]) => {
        if (normalizedFilter && group.toLowerCase() !== normalizedFilter) return false;
        return true;
      })
      .map(([entity, metrics]) => {
        const entityLower = entity.toLowerCase();
        const filteredMetrics = metrics.filter((m) => {
          if (allowedMetrics && !allowedMetrics.has(m.name)) return false;
          const matchesSearch =
            m.name.toLowerCase().includes(search.toLowerCase()) ||
            entityLower.includes(search.toLowerCase());
          return matchesSearch;
        });
        return [entity, filteredMetrics] as [string, typeof metrics];
      })
      .filter(([, metrics]) => metrics.length > 0);
  }, [groupedMetrics, entityFilter, search, allowedMetrics]);

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-white/10">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search metrics..."
            className="w-full bg-[#151821] border border-white/10 rounded-lg py-2 pl-9 pr-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {/* Show grain context when metrics are selected */}
        {selectedMetrics.length > 0 && context?.base_grain && (
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-1">
            <Layers className="w-3 h-3" />
            <span>Base grain: <span className="text-cyan-400">{context.base_grain.join(', ')}</span></span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {error ? (
          <div className="text-center text-red-400 py-8">
            Failed to load metrics. Check that the API is running. <span className="text-xs text-slate-400">{String(error)}</span>
          </div>
        ) : isLoading ? (
          <div className="text-center text-slate-500 py-8">Loading metrics...</div>
        ) : filteredGroups.length === 0 ? (
          <div className="text-center text-slate-500 py-8">
            No metrics found. Ensure the API responds at /api/metrics.
          </div>
        ) : (
          <>
            {filteredGroups.map(([entity, metrics]) => (
              <div key={entity}>
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                  {entity}
                </h3>
                <div className="space-y-1">
                  {metrics
                    .filter((m) =>
                      m.name.toLowerCase().includes(search.toLowerCase())
                    )
                    .map((metric) => {
                      const isSelected = selectedMetrics.includes(metric.name);
                      const meta = metricMeta.get(metric.name);
                      const badge = meta && selectedMetrics.length > 0 ? getCompatibilityBadge(meta.reason) : null;

                      return (
                        <button
                          key={metric.id}
                          onClick={() => onToggle(metric.name)}
                          className={`w-full text-left p-2 rounded-lg transition-colors flex items-center gap-2 ${isSelected
                              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                              : 'hover:bg-white/5 text-slate-300'
                            }`}
                        >
                          <div
                            className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 ${isSelected
                                ? 'border-cyan-400 bg-cyan-500/20'
                                : 'border-slate-500'
                              }`}
                          >
                            {isSelected && <Check className="w-3 h-3" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium truncate">{metric.name}</span>
                              {badge && !isSelected && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded ${badge.color}`}>
                                  {badge.label}
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500">{metric.type}</div>
                          </div>
                        </button>
                      );
                    })}
                </div>
              </div>
            ))}

            {/* Show excluded metrics toggle */}
            {selectedMetrics.length > 0 && excludedMetrics.length > 0 && (
              <div className="border-t border-white/10 pt-4">
                <button
                  onClick={() => setShowExcluded(!showExcluded)}
                  className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-400"
                >
                  <AlertCircle className="w-3 h-3" />
                  {showExcluded ? 'Hide' : 'Show'} {excludedMetrics.length} incompatible metrics
                </button>

                {showExcluded && (
                  <div className="mt-3 space-y-1">
                    {excludedMetrics.map((m: ExcludedMetric) => (
                      <div
                        key={m.name}
                        className="p-2 rounded-lg bg-red-500/5 border border-red-500/10 text-slate-500"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-400">{m.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">
                            {m.reason === 'grain_incompatible' && 'Grain mismatch'}
                            {m.reason === 'grain_unknown' && 'Unknown grain'}
                            {m.reason === 'no_relationship_path' && 'No join path'}
                          </span>
                        </div>
                        {m.model && (
                          <div className="text-xs mt-0.5">Model: {m.model}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
