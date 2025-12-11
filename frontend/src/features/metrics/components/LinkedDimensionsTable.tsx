import React from 'react';
import { Link } from 'react-router-dom';
import { Layers, Loader2 } from 'lucide-react';
import type { LinkedDimension } from '../api/getMetricDimensions';

interface LinkedDimensionsTableProps {
  dimensions: LinkedDimension[];
  isLoading?: boolean;
}

export const LinkedDimensionsTable: React.FC<LinkedDimensionsTableProps> = ({
  dimensions,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-10 flex justify-center">
        <Loader2 className="animate-spin text-cyan-500 w-6 h-6" />
      </div>
    );
  }

  if (dimensions.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500 italic rounded-xl border border-white/10 bg-[#151821]">
        No dimensions linked to this metric
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
      <table className="w-full text-left">
        <thead className="bg-white/5 border-b border-white/10">
          <tr>
            <th className="p-4 font-semibold text-slate-300">Name</th>
            <th className="p-4 font-semibold text-slate-300">Type</th>
            <th className="p-4 font-semibold text-slate-300">Cardinality</th>
            <th className="p-4 font-semibold text-slate-300">Description</th>
            <th className="p-4 font-semibold text-slate-300">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {dimensions.map((dim) => (
            <tr key={dim.id} className="hover:bg-white/5 transition-colors">
              <td className="p-4 font-bold text-white">{dim.name}</td>
              <td className="p-4">
                <span className="px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 text-xs font-mono">
                  {dim.type}
                </span>
              </td>
              <td className="p-4 text-slate-400">
                {dim.cardinality !== null ? dim.cardinality.toLocaleString() : '—'}
              </td>
              <td className="p-4 text-slate-400 text-sm max-w-md">
                {dim.description || '—'}
              </td>
              <td className="p-4">
                <Link
                  to={`/dimensions/${dim.id}`}
                  className="text-sm font-medium text-cyan-400 hover:underline flex items-center gap-1"
                >
                  <Layers className="w-4 h-4" />
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

