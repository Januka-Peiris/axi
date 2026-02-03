import React from 'react';
import { GitCommit, Loader2 } from 'lucide-react';
import type { MetricVersionRecord } from '../api/getMetricVersions';

interface ServerMetricVersionHistoryProps {
  versions: MetricVersionRecord[];
  isLoading: boolean;
  metricName: string;
}

const statusStyles: Record<string, string> = {
  active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  deprecated: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  disabled: 'bg-red-500/10 text-red-400 border-red-500/20',
};

export const ServerMetricVersionHistory: React.FC<ServerMetricVersionHistoryProps> = ({
  versions,
  isLoading,
  metricName,
}) => {
  const formatDate = (s: string) => {
    try {
      const d = new Date(s);
      return d.toLocaleDateString(undefined, { dateStyle: 'medium' }) + ' ' + d.toLocaleTimeString(undefined, { timeStyle: 'short' });
    } catch {
      return s;
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <GitCommit className="w-4 h-4" />
          Version history
        </h3>
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading…
        </div>
      </div>
    );
  }

  if (!versions || versions.length === 0) {
    return (
      <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
          <GitCommit className="w-4 h-4" />
          Version history
        </h3>
        <p className="text-slate-500 text-sm">No version history yet. Promote or deprecate this metric to create records.</p>
      </div>
    );
  }

  return (
    <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
      <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
        <GitCommit className="w-4 h-4" />
        Version history
      </h3>
      <div className="space-y-0 relative">
        {/* vertical line */}
        <div className="absolute left-[11px] top-2 bottom-2 w-px bg-white/10" />
        {versions.map((v, idx) => (
          <div key={v.id} className="relative flex gap-4 pb-6 last:pb-0">
            <div className="relative z-10 w-6 h-6 rounded-full bg-[#151821] border-2 border-cyan-500/50 flex items-center justify-center flex-shrink-0">
              <div className="w-2 h-2 rounded-full bg-cyan-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-white font-semibold">v{v.version}</span>
                <span className={`px-2 py-0.5 rounded border text-xs font-medium capitalize ${statusStyles[v.status] ?? 'bg-white/5 text-slate-400'}`}>
                  {v.status}
                </span>
                {v.replacement_metric && (
                  <span className="text-xs text-slate-500">
                    → {v.replacement_metric}
                  </span>
                )}
              </div>
              <p className="text-slate-500 text-xs mt-0.5">{formatDate(v.created_at)}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
