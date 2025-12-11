import React, { useState } from 'react';
import { Search, Check } from 'lucide-react';
import { useDimensionsForQuery } from '../api/listDimensions';
import { useReachableDimensions } from '../api/getReachableDimensions';

interface DimensionSelectorProps {
  selectedDimensions: string[];
  selectedMetrics: string[]; // Add this prop to filter dimensions
  onToggle: (dimensionName: string) => void;
}

export const DimensionSelector: React.FC<DimensionSelectorProps> = ({
  selectedDimensions,
  selectedMetrics,
  onToggle,
}) => {
  const { groupedDimensions, isLoading } = useDimensionsForQuery();
  const { data: reachableDimensions = [], isLoading: reachableLoading } = useReachableDimensions(selectedMetrics);
  const [search, setSearch] = useState('');
  
  // Filter dimensions to only show reachable ones when metrics are selected
  const reachableSet = new Set(reachableDimensions);
  const shouldFilter = selectedMetrics.length > 0 && reachableDimensions.length > 0;

  const filteredGroups = Object.entries(groupedDimensions).filter(([entity]) =>
    entity.toLowerCase().includes(search.toLowerCase())
  );

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
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {isLoading || reachableLoading ? (
          <div className="text-center text-slate-500 py-8">Loading dimensions...</div>
        ) : shouldFilter && reachableDimensions.length === 0 ? (
          <div className="text-center text-slate-500 py-8">
            <div className="mb-2">No shared dimensions available</div>
            <div className="text-xs text-slate-600">for the selected metrics</div>
          </div>
        ) : filteredGroups.length === 0 ? (
          <div className="text-center text-slate-500 py-8">No dimensions found</div>
        ) : (
          filteredGroups.map(([entity, dimensions]) => (
            <div key={entity}>
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                {entity}
              </h3>
              <div className="space-y-1">
                {dimensions
                  .filter((d) => {
                    // Filter by search
                    if (!d.name.toLowerCase().includes(search.toLowerCase())) {
                      return false;
                    }
                    // Filter by reachability if metrics are selected
                    if (shouldFilter && !reachableSet.has(d.name)) {
                      return false;
                    }
                    return true;
                  })
                  .map((dimension) => {
                    const isSelected = selectedDimensions.includes(dimension.name);
                    return (
                      <button
                        key={dimension.id}
                        onClick={() => onToggle(dimension.name)}
                        className={`w-full text-left p-2 rounded-lg transition-colors flex items-center gap-2 ${
                          isSelected
                            ? 'bg-violet-500/10 text-violet-400 border border-violet-500/20'
                            : 'hover:bg-white/5 text-slate-300'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                            isSelected
                              ? 'border-violet-400 bg-violet-500/20'
                              : 'border-slate-500'
                          }`}
                        >
                          {isSelected && <Check className="w-3 h-3" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{dimension.name}</div>
                          <div className="text-xs text-slate-500">{dimension.data_type}</div>
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

