import React, { useMemo, useState } from 'react';
import { Search, Check } from 'lucide-react';
import { useMetricsForQuery } from '../api/listMetrics';

interface MetricSelectorProps {
  selectedMetrics: string[];
  onToggle: (metricName: string) => void;
  entityFilter?: string;
}

export const MetricSelector: React.FC<MetricSelectorProps> = ({
  selectedMetrics,
  onToggle,
  entityFilter,
}) => {
  const { groupedMetrics, isLoading, error } = useMetricsForQuery();
  const [search, setSearch] = useState('');

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
          const matchesSearch =
            m.name.toLowerCase().includes(search.toLowerCase()) ||
            entityLower.includes(search.toLowerCase());
          return matchesSearch;
        });
        return [entity, filteredMetrics] as [string, typeof metrics];
      })
      .filter(([, metrics]) => metrics.length > 0);
  }, [groupedMetrics, entityFilter, search]);

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
          filteredGroups.map(([entity, metrics]) => (
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
                          className={`w-4 h-4 rounded border-2 flex items-center justify-center ${isSelected
                              ? 'border-cyan-400 bg-cyan-500/20'
                              : 'border-slate-500'
                            }`}
                        >
                          {isSelected && <Check className="w-3 h-3" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{metric.name}</div>
                          <div className="text-xs text-slate-500">{metric.type}</div>
                        </div>
                      </button>
                    );
                  })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
