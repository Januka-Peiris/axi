import React, { useState } from 'react';
import { Search, Check } from 'lucide-react';
import { useMetricsForQuery } from '../api/listMetrics';

interface MetricSelectorProps {
  selectedMetrics: string[];
  onToggle: (metricName: string) => void;
}

export const MetricSelector: React.FC<MetricSelectorProps> = ({
  selectedMetrics,
  onToggle,
}) => {
  const { groupedMetrics, isLoading } = useMetricsForQuery();
  const [search, setSearch] = useState('');

  const filteredGroups = Object.entries(groupedMetrics).filter(([entity]) =>
    entity.toLowerCase().includes(search.toLowerCase())
  );

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
        {isLoading ? (
          <div className="text-center text-slate-500 py-8">Loading metrics...</div>
        ) : filteredGroups.length === 0 ? (
          <div className="text-center text-slate-500 py-8">No metrics found</div>
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
                        className={`w-full text-left p-2 rounded-lg transition-colors flex items-center gap-2 ${
                          isSelected
                            ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                            : 'hover:bg-white/5 text-slate-300'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                            isSelected
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

