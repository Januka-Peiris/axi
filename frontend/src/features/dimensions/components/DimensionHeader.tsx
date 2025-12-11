import React from 'react';
import { Key, Type } from 'lucide-react';
import type { DimensionDetail } from '../api/getDimension';

interface DimensionHeaderProps {
  dimension: DimensionDetail;
}

export const DimensionHeader: React.FC<DimensionHeaderProps> = ({ dimension }) => {
  return (
    <div className="space-y-4 border-b border-white/10 pb-8">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <h1 className="text-3xl font-black text-white">{dimension.name}</h1>
            {dimension.entity_name && (
              <span className="px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-sm font-bold uppercase tracking-wider">
                {dimension.entity_name}
              </span>
            )}
            <span className="px-2 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30 text-xs font-bold uppercase tracking-wider flex items-center gap-1">
              <Type className="w-3 h-3" />
              {dimension.data_type}
            </span>
            {dimension.is_primary && (
              <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-bold uppercase tracking-wider flex items-center gap-1">
                <Key className="w-3 h-3" />
                Primary Key
              </span>
            )}
            {dimension.cardinality !== null && (
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-mono">
                {dimension.cardinality.toLocaleString()} values
              </span>
            )}
          </div>
          {dimension.description && (
            <p className="text-lg text-slate-400 max-w-3xl">{dimension.description}</p>
          )}
        </div>
      </div>
    </div>
  );
};

