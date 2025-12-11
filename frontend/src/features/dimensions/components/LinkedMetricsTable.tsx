import React from 'react';
import { Link } from 'react-router-dom';
import { Activity, Loader2 } from 'lucide-react';
import type { LinkedMetric } from '../api/getDimensionMetrics';

interface LinkedMetricsTableProps {
  metrics: LinkedMetric[];
  isLoading?: boolean;
}

export const LinkedMetricsTable: React.FC<LinkedMetricsTableProps> = ({
  metrics,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-10 flex justify-center">
        <Loader2 className="animate-spin text-cyan-500 w-6 h-6" />
      </div>
    );
  }

  if (metrics.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500 italic rounded-xl border border-white/10 bg-[#151821]">
        No metrics linked to this dimension
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
      <table className="w-full text-left">
        <thead className="bg-white/5 border-b border-white/10">
          <tr>
            <th className="p-4 font-semibold text-slate-300">Metric Name</th>
            <th className="p-4 font-semibold text-slate-300">Type</th>
            <th className="p-4 font-semibold text-slate-300">Description</th>
            <th className="p-4 font-semibold text-slate-300">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {metrics.map((metric) => (
            <tr key={metric.id} className="hover:bg-white/5 transition-colors">
              <td className="p-4 font-bold text-white">{metric.name}</td>
              <td className="p-4">
                <span className="px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 text-xs font-mono">
                  {metric.type}
                </span>
              </td>
              <td className="p-4 text-slate-400 text-sm max-w-md">
                {metric.description || '—'}
              </td>
              <td className="p-4">
                <Link
                  to={`/metrics/${metric.id || metric.name}`}
                  className="text-sm font-medium text-cyan-400 hover:underline flex items-center gap-1"
                >
                  <Activity className="w-4 h-4" />
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

