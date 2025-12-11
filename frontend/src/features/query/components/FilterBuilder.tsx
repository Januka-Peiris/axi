import React from 'react';
import { X, Plus } from 'lucide-react';
import type { FilterItem } from '../api/runSemanticQuery';

interface FilterBuilderProps {
  filters: FilterItem[];
  availableDimensions: string[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, filter: FilterItem) => void;
}

const OPERATORS = ['=', '!=', '>', '<', '>=', '<=', 'IN'] as const;

export const FilterBuilder: React.FC<FilterBuilderProps> = ({
  filters,
  availableDimensions,
  onAdd,
  onRemove,
  onUpdate,
}) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Filters</h3>
        <button
          onClick={onAdd}
          className="flex items-center gap-1 px-3 py-1 text-xs bg-white/5 hover:bg-white/10 rounded border border-white/10 transition-colors"
        >
          <Plus className="w-3 h-3" />
          Add Filter
        </button>
      </div>

      {filters.length === 0 ? (
        <div className="text-sm text-slate-500 italic p-4 bg-[#151821] rounded border border-white/10">
          No filters added. Click "Add Filter" to add one.
        </div>
      ) : (
        <div className="space-y-2">
          {filters.map((filter, index) => (
            <div
              key={index}
              className="flex items-center gap-2 p-3 bg-[#151821] rounded border border-white/10"
            >
              <select
                value={filter.dimension}
                onChange={(e) =>
                  onUpdate(index, { ...filter, dimension: e.target.value })
                }
                className="flex-1 bg-[#0d0f15] border border-white/10 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500/50"
              >
                <option value="">Select dimension...</option>
                {availableDimensions.map((dim) => (
                  <option key={dim} value={dim}>
                    {dim}
                  </option>
                ))}
              </select>

              <select
                value={filter.op}
                onChange={(e) =>
                  onUpdate(index, {
                    ...filter,
                    op: e.target.value as FilterItem['op'],
                  })
                }
                className="bg-[#0d0f15] border border-white/10 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500/50"
              >
                {OPERATORS.map((op) => (
                  <option key={op} value={op}>
                    {op}
                  </option>
                ))}
              </select>

              <input
                type="text"
                value={filter.value || ''}
                onChange={(e) => {
                  let value: any = e.target.value;
                  // Handle IN operator - expect comma-separated values
                  if (filter.op === 'IN') {
                    value = value.split(',').map((v: string) => v.trim()).filter(Boolean);
                  }
                  onUpdate(index, { ...filter, value });
                }}
                placeholder={filter.op === 'IN' ? 'value1, value2...' : 'value'}
                className="flex-1 bg-[#0d0f15] border border-white/10 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500/50"
              />

              <button
                onClick={() => onRemove(index)}
                className="text-slate-400 hover:text-red-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

