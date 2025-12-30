import React, { useMemo, useState } from 'react';
import { Search, Check, Link2, AlertCircle } from 'lucide-react';
import { useDimensionsForQuery } from '../api/listDimensions';
import { useSqlRunnerContext } from '../api/getSqlRunnerContext';
import type { VisibleDimension, ExcludedDimension } from '../api/getSqlRunnerContext';

interface DimensionSelectorProps {
  selectedDimensions: string[];
  selectedMetrics: string[]; // Add this prop to filter dimensions
  entity?: string;
  onToggle: (dimensionName: string) => void;
}

// Helper to get a human-readable relationship description
const getRelationshipBadge = (dim: VisibleDimension) => {
  if (dim.hops === 0) {
    return { label: 'Direct', color: 'text-emerald-400 bg-emerald-500/10' };
  }
  if (dim.relationship_type === 'explicit') {
    return { label: `${dim.hops} hop${dim.hops > 1 ? 's' : ''}`, color: 'text-cyan-400 bg-cyan-500/10' };
  }
  return { label: 'Inferred', color: 'text-amber-400 bg-amber-500/10' };
};

export const DimensionSelector: React.FC<DimensionSelectorProps> = ({
  selectedDimensions,
  selectedMetrics,
  entity,
  onToggle,
}) => {
  const { groupedDimensions, isLoading } = useDimensionsForQuery();
  const contextQuery = useSqlRunnerContext(selectedMetrics, []);
  const context = contextQuery.data;
  const ctxLoading = contextQuery.isLoading;
  const [search, setSearch] = useState('');
  const [showExcluded, setShowExcluded] = useState(false);

  // Build lookup maps for dimension metadata
  const dimensionMeta = useMemo(() => {
    const map = new Map<string, VisibleDimension>();
    (context?.visible_dimensions || []).forEach((d: VisibleDimension) => {
      map.set(d.name, d);
    });
    return map;
  }, [context?.visible_dimensions]);

  // Filter dimensions to only show reachable ones when metrics are selected
  const reachableSet = useMemo(
    () => new Set((context?.visible_dimensions || []).map((d: VisibleDimension) => d.name)),
    [context?.visible_dimensions]
  );
  const shouldFilter = selectedMetrics.length > 0 && reachableSet.size > 0;
  const excludedDimensions = context?.excluded_dimensions || [];

  const filteredGroups = useMemo(() => {
    const normalizedEntity = (entity || '').toLowerCase();
    return Object.entries(groupedDimensions)
      .filter(([group]) => {
        if (normalizedEntity && group.toLowerCase() !== normalizedEntity) return false;
        return true;
      })
      .map(([group, dims]) => {
        const filteredDims = dims.filter((d) => {
          const matchesSearch =
            d.name.toLowerCase().includes(search.toLowerCase()) ||
            group.toLowerCase().includes(search.toLowerCase());
          if (!matchesSearch) return false;
          if (shouldFilter && !reachableSet.has(d.name)) return false;
          return true;
        });
        return [group, filteredDims] as [string, typeof dims];
      })
      .filter(([, dims]) => dims.length > 0);
  }, [groupedDimensions, entity, search, shouldFilter, reachableSet]);

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-white/10">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search dimensions..."
            className="w-full bg-[#151821] border border-white/10 rounded-lg py-2 pl-9 pr-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {/* Show relationship context when metrics are selected */}
        {selectedMetrics.length > 0 && context?.base_model && (
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-1">
            <Link2 className="w-3 h-3" />
            <span>Showing dimensions reachable from <span className="text-cyan-400">{context.base_model}</span></span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {isLoading || ctxLoading ? (
          <div className="text-center text-slate-500 py-8">Loading dimensions...</div>
        ) : shouldFilter && reachableSet.size === 0 ? (
          <div className="text-center text-slate-500 py-8">
            <div className="mb-2">No shared dimensions available</div>
            <div className="text-xs text-slate-600">for the selected metrics</div>
            {excludedDimensions.length > 0 && (
              <button
                onClick={() => setShowExcluded(!showExcluded)}
                className="mt-3 text-xs text-amber-400 hover:text-amber-300"
              >
                {showExcluded ? 'Hide' : 'Show'} {excludedDimensions.length} excluded dimensions
              </button>
            )}
          </div>
        ) : filteredGroups.length === 0 ? (
          <div className="text-center text-slate-500 py-8">No dimensions found</div>
        ) : (
          <>
            {filteredGroups.map(([entityName, dimensions]) => (
              <div key={entityName}>
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                  {entityName}
                </h3>
                <div className="space-y-1">
                  {dimensions
                    .filter((d) => {
                      if (!d.name.toLowerCase().includes(search.toLowerCase())) {
                        return false;
                      }
                      if (shouldFilter && !reachableSet.has(d.name)) {
                        return false;
                      }
                      return true;
                    })
                    .map((dimension) => {
                      const isSelected = selectedDimensions.includes(dimension.name);
                      const meta = dimensionMeta.get(dimension.name);
                      const badge = meta ? getRelationshipBadge(meta) : null;

                      return (
                        <button
                          key={dimension.id}
                          onClick={() => onToggle(dimension.name)}
                          className={`w-full text-left p-2 rounded-lg transition-colors flex items-center gap-2 ${
                            isSelected
                              ? 'bg-violet-500/10 text-violet-400 border border-violet-500/20'
                              : 'hover:bg-white/5 text-slate-300'
                          }`}
                          title={meta?.via_description || undefined}
                        >
                          <div
                            className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                              isSelected
                                ? 'border-violet-400 bg-violet-500/20'
                                : 'border-slate-500'
                            }`}
                          >
                            {isSelected && <Check className="w-3 h-3" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium truncate">{dimension.name}</span>
                              {badge && selectedMetrics.length > 0 && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded ${badge.color}`}>
                                  {badge.label}
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500 flex items-center gap-1">
                              <span>{dimension.data_type}</span>
                              {meta?.via_description && meta.hops > 0 && (
                                <span className="text-slate-600">• via {meta.via_description}</span>
                              )}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                </div>
              </div>
            ))}

            {/* Show excluded dimensions toggle */}
            {shouldFilter && excludedDimensions.length > 0 && (
              <div className="border-t border-white/10 pt-4">
                <button
                  onClick={() => setShowExcluded(!showExcluded)}
                  className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-400"
                >
                  <AlertCircle className="w-3 h-3" />
                  {showExcluded ? 'Hide' : 'Show'} {excludedDimensions.length} excluded dimensions
                </button>

                {showExcluded && (
                  <div className="mt-3 space-y-1">
                    {excludedDimensions.map((dim: ExcludedDimension) => (
                      <div
                        key={dim.name}
                        className="p-2 rounded-lg bg-red-500/5 border border-red-500/10 text-slate-500"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-400">{dim.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">
                            {dim.reason === 'no_relationship_path' && 'No join path'}
                            {dim.reason === 'grain_incompatible' && 'Grain mismatch'}
                            {dim.reason === 'metric_grain_unknown' && 'Unknown grain'}
                          </span>
                        </div>
                        {dim.entity && (
                          <div className="text-xs mt-0.5">Entity: {dim.entity}</div>
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
