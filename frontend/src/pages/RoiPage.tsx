import React from 'react';
import { Link } from 'react-router-dom';
import { BarChart3, Loader2, TrendingDown, Clock, AlertTriangle } from 'lucide-react';
import { useRoiSummary } from '../api/roi';

export const RoiPage: React.FC = () => {
  const { data, isLoading, error } = useRoiSummary(20);

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-6">Adoption & ROI</h1>
        <div className="flex items-center gap-2 text-slate-500 py-12">
          <Loader2 className="w-6 h-6 animate-spin" />
          Loading summary…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-6">Adoption & ROI</h1>
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
          <p className="text-amber-200">Unable to load ROI summary. Ensure usage ingestion has run.</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const deprecatedDeclining =
    data.deprecated_previous_7_days > 0 &&
    data.deprecated_last_7_days < data.deprecated_previous_7_days;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white mb-2">Adoption & ROI</h1>
        <p className="text-slate-500 text-sm">
          Lightweight summary of metric usage and estimated analyst time saved. Config-driven; read-only warehouse
          data.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-[#151821] border border-white/10">
          <div className="flex items-center gap-2 text-slate-500 text-sm font-medium uppercase tracking-wider mb-2">
            <BarChart3 className="w-4 h-4" />
            Matched queries
          </div>
          <div className="text-2xl font-bold text-white tabular-nums">{data.total_matched_queries}</div>
        </div>
        <div className="p-5 rounded-xl bg-[#151821] border border-white/10">
          <div className="flex items-center gap-2 text-slate-500 text-sm font-medium uppercase tracking-wider mb-2">
            <AlertTriangle className="w-4 h-4" />
            Deprecated access (total)
          </div>
          <div className="text-2xl font-bold tabular-nums text-amber-400">{data.total_deprecated_access}</div>
        </div>
        <div className="p-5 rounded-xl bg-[#151821] border border-white/10">
          <div className="flex items-center gap-2 text-slate-500 text-sm font-medium uppercase tracking-wider mb-2">
            <TrendingDown className="w-4 h-4" />
            Deprecated trend
          </div>
          <div className="text-sm text-slate-300">
            Last 7d: <span className="font-mono text-amber-400">{data.deprecated_last_7_days}</span>
            {' · '}
            Prev 7d: <span className="font-mono text-slate-400">{data.deprecated_previous_7_days}</span>
            {deprecatedDeclining && (
              <span className="ml-2 text-emerald-400 text-xs font-medium">Declining</span>
            )}
          </div>
        </div>
        <div className="p-5 rounded-xl bg-[#151821] border border-white/10">
          <div className="flex items-center gap-2 text-slate-500 text-sm font-medium uppercase tracking-wider mb-2">
            <Clock className="w-4 h-4" />
            Est. hours saved
          </div>
          <div className="text-2xl font-bold text-cyan-400 tabular-nums">
            {data.estimated_analyst_hours_saved.toFixed(1)}h
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {data.hours_saved_per_query}h per query (config-driven)
          </p>
        </div>
      </div>

      {/* Top metrics */}
      <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
        <h2 className="text-lg font-bold text-white mb-4">Top used metrics</h2>
        {data.top_metrics && data.top_metrics.length > 0 ? (
          <div className="rounded-lg border border-white/10 overflow-hidden">
            <table className="w-full text-left">
              <thead className="bg-white/5 border-b border-white/10">
                <tr>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase">Metric</th>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase text-right">Usage</th>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase text-right">Deprecated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.top_metrics.map((m) => (
                  <tr key={m.metric_name} className="hover:bg-white/5">
                    <td className="p-3">
                      <Link
                        to={`/metrics/${encodeURIComponent(m.metric_name)}`}
                        className="text-cyan-400 hover:underline font-medium"
                      >
                        {m.metric_name}
                      </Link>
                    </td>
                    <td className="p-3 text-slate-300 text-right tabular-nums">{m.usage_count}</td>
                    <td className="p-3 text-right tabular-nums">
                      {m.deprecated_access_count > 0 ? (
                        <span className="text-amber-400">{m.deprecated_access_count}</span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-500 text-sm">No usage data yet. Run Snowflake ingestion to match queries.</p>
        )}
      </div>
    </div>
  );
};
