import React from 'react';
import { Loader2 } from 'lucide-react';
import type { LinkedEntity } from '../api/getMetricEntities';

interface LinkedEntitiesTableProps {
  entities: LinkedEntity[];
  isLoading?: boolean;
}

export const LinkedEntitiesTable: React.FC<LinkedEntitiesTableProps> = ({
  entities,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-10 flex justify-center">
        <Loader2 className="animate-spin text-cyan-500 w-6 h-6" />
      </div>
    );
  }

  if (entities.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500 italic rounded-xl border border-white/10 bg-[#151821]">
        No entities linked to this metric
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
      <table className="w-full text-left">
        <thead className="bg-white/5 border-b border-white/10">
          <tr>
            <th className="p-4 font-semibold text-slate-300">Entity Name</th>
            <th className="p-4 font-semibold text-slate-300">Model</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {entities.map((entity, idx) => (
            <tr key={idx} className="hover:bg-white/5 transition-colors">
              <td className="p-4 font-bold text-white font-mono">{entity.name}</td>
              <td className="p-4 text-slate-400 font-mono text-sm">{entity.model || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

