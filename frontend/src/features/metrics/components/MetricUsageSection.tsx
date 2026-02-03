import React from 'react';
import { BarChart3, Loader2, AlertTriangle, Calendar } from 'lucide-react';
import { useMetricUsage } from '../api/getMetricUsage';
import type { MetricUsageByVersion } from '../api/getMetricUsage';

interface MetricUsageSectionProps {
  metricId: string;
}

function VersionRow({ v }: { v: MetricUsageByVersion }) {
  return (
    <tr className="border-b border-white/5 last:border-0 hover:bg-white/5">
      <td className="p-3 font-mono text-slate-300 text-sm">v{v.version}</td>
      <td className="p-3 text-slate-400 text-sm tabular-nums">{v.usage_count}</td>
      <td className="p-3 text-slate-400 text-sm tabular-nums">
        {v.deprecated_access_count > 0 ? (
          <span className="text-amber-400">{v.deprecated_access_count}</span>
        ) : (
          '—'
        )}
      </td>
      <td className="p-3 text-slate-500 text-xs">
        {v.first_seen ? new Date(v.first_seen).toLocaleDateString() : '—'}
      </td>
      <td className="p-3 text-slate-500 text-xs">
        {v.last_seen ? new Date(v.last_seen).toLocaleDateString() : '—'}
      </td>
    </tr>
  );
}

export const MetricUsageSection: React.FC<MetricUsageSectionProps> = ({ metricId }) => {
  const { data, isLoading, error } = useMetricUsage(metricId);

  if (isLoading) {
    return (
      <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          Usage
        </h3>
        <div className="flex items-center gap-2 text-slate-500 py-6">
          <Loader2 className="w-5 h-5 animate-spin" />
          Loading usage…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          Usage
        </h3>
        <p className="text-amber-400 text-sm">Usage data unavailable.</p>
      </div>
    );
  }

  if (!data) return null;

  const hasDeprecatedUsage = data.total_deprecated_access_count > 0;

  return (
    <div className="p-6 rounded-xl bg-[#151821] border border-white/10 space-y-4">
      <h3 className="text-lg font-bold text-white flex items-center gap-2">
        <BarChart3 className="w-5 h-5 text-cyan-400" />
        Usage
      </h3>
      <p className="text-sm text-slate-500">
        Matched query runs from warehouse logs (read-only). First/last seen reflect when this metric was used.
      </p>

      {hasDeprecatedUsage && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-amber-200 text-sm font-medium">Deprecated access detected</p>
            <p className="text-slate-400 text-xs mt-0.5">
              {data.total_deprecated_access_count} query run(s) used a deprecated version of this metric. Prefer the
              current or replacement metric.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-3 rounded-lg bg-white/5 border border-white/5">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total runs</div>
          <div className="text-xl font-bold text-white tabular-nums mt-1">{data.total_usage_count}</div>
        </div>
        <div className="p-3 rounded-lg bg-white/5 border border-white/5">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Deprecated runs</div>
          <div className="text-xl font-bold tabular-nums mt-1">
            <span className={data.total_deprecated_access_count > 0 ? 'text-amber-400' : 'text-slate-400'}>
              {data.total_deprecated_access_count}
            </span>
          </div>
        </div>
        <div className="p-3 rounded-lg bg-white/5 border border-white/5 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-500" />
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">First seen</div>
            <div className="text-sm text-slate-300 mt-1">
              {data.first_seen ? new Date(data.first_seen).toLocaleDateString() : '—'}
            </div>
          </div>
        </div>
        <div className="p-3 rounded-lg bg-white/5 border border-white/5 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-500" />
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Last seen</div>
            <div className="text-sm text-slate-300 mt-1">
              {data.last_seen ? new Date(data.last_seen).toLocaleDateString() : '—'}
            </div>
          </div>
        </div>
      </div>

      {data.by_version && data.by_version.length > 0 && (
        <>
          <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider">By version</h4>
          <div className="rounded-lg border border-white/10 overflow-hidden">
            <table className="w-full text-left">
              <thead className="bg-white/5 border-b border-white/10">
                <tr>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase">Version</th>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase">Runs</th>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase">Deprecated</th>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase">First seen</th>
                  <th className="p-3 font-semibold text-slate-400 text-xs uppercase">Last seen</th>
                </tr>
              </thead>
              <tbody>
                {data.by_version.map((v) => (
                  <VersionRow key={v.version} v={v} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {(!data.by_version || data.by_version.length === 0) && data.total_usage_count === 0 && (
        <p className="text-slate-500 text-sm">No usage recorded yet. Run ingestion to match warehouse queries.</p>
      )}
    </div>
  );
};
