import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpDown, ArrowUp, ArrowDown, Search, BarChart3, Loader2, Plus } from 'lucide-react';
import { useMetrics } from './api/getMetrics';
import type { MetricStatus } from './api/getMetrics';
import { MetricBuilder } from './components/MetricBuilder';

const StatusBadge: React.FC<{ status: MetricStatus }> = ({ status }) => {
  const styles =
    status === 'active'
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
      : status === 'deprecated'
        ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
        : 'bg-red-500/10 text-red-400 border-red-500/20';
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-medium capitalize ${styles}`}>
      {status}
    </span>
  );
};

type SortField = 'name' | 'entity_name' | 'type';
type SortDirection = 'asc' | 'desc';

const SortIcon: React.FC<{ field: SortField; activeField: SortField; direction: SortDirection }> = ({
  field,
  activeField,
  direction,
}) => {
  if (activeField !== field) {
    return <ArrowUpDown className="w-3 h-3 text-slate-500" />;
  }
  return direction === 'asc' ? (
    <ArrowUp className="w-3 h-3 text-cyan-400" />
  ) : (
    <ArrowDown className="w-3 h-3 text-cyan-400" />
  );
};

export const MetricsListPage: React.FC = () => {
  const { data: metrics, isLoading, error } = useMetrics();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [showBuilder, setShowBuilder] = useState(false);

  // Get unique types for filter
  const uniqueTypes = useMemo(() => {
    const types = new Set<string>();
    metrics?.forEach((m) => {
      if (m.type) types.add(m.type);
    });
    return Array.from(types).sort();
  }, [metrics]);

  // Filter and sort metrics
  const filteredAndSorted = useMemo(() => {
    if (!metrics) return [];

    const filtered = metrics.filter((m) => {
      const matchesSearch =
        m.name.toLowerCase().includes(search.toLowerCase()) ||
        (m.entity_name?.toLowerCase().includes(search.toLowerCase()) ?? false) ||
        m.type.toLowerCase().includes(search.toLowerCase());
      const matchesType = !typeFilter || m.type === typeFilter;
      return matchesSearch && matchesType;
    });

    const sorted = [...filtered].sort((a, b) => {
      let aVal: string;
      let bVal: string;

      switch (sortField) {
        case 'name':
          aVal = a.name;
          bVal = b.name;
          break;
        case 'entity_name':
          aVal = a.entity_name || '';
          bVal = b.entity_name || '';
          break;
        case 'type':
          aVal = a.type;
          bVal = b.type;
          break;
        default:
          return 0;
      }

      return sortDirection === 'asc'
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    });

    return sorted;
  }, [metrics, search, typeFilter, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const truncate = (text: string | null, maxLength: number = 60) => {
    if (!text) return '—';
    return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
  };

  return (
    <>
      {showBuilder && (
        <MetricBuilder
          onClose={() => setShowBuilder(false)}
          onSuccess={() => setShowBuilder(false)}
        />
      )}
      <div className="max-w-7xl mx-auto space-y-8 pb-20">
        {/* Breadcrumbs */}
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Link to="/" className="hover:text-white transition-colors">
            Home
          </Link>
          <span>/</span>
          <span className="text-white">Metrics</span>
        </div>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 className="w-8 h-8 text-cyan-400" />
              <h1 className="text-3xl font-black text-white">Metrics</h1>
            </div>
            <p className="text-slate-400">
              Browse and explore all metrics in your semantic layer
            </p>
          </div>
          <button
            onClick={() => setShowBuilder(true)}
            className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white rounded-lg font-medium flex items-center gap-2"
          >
            <Plus size={16} />
            Create Metric
          </button>
        </div>

      {/* Content */}
      {error ? (
        <div className="p-8 text-center text-red-400 rounded-xl border border-red-500/20 bg-red-500/10">
          Failed to load metrics. Please try again later.
        </div>
      ) : isLoading ? (
        <div className="p-10 flex justify-center">
          <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
        </div>
      ) : (
        <div className="space-y-4">
          {/* Search and Filters */}
          <div className="flex gap-4 items-center">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search metrics, entities, or types..."
                className="w-full bg-[#151821] border border-white/10 rounded-lg py-2 pl-9 pr-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-[#151821] border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
            >
              <option value="">All Types</option>
              {uniqueTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          {/* Table */}
          <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
            <table className="w-full text-left">
              <thead className="bg-white/5 border-b border-white/10">
                <tr>
                  <th className="p-4 font-semibold text-slate-300">
                    <button
                      onClick={() => handleSort('name')}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      Metric Name
                      <SortIcon field="name" activeField={sortField} direction={sortDirection} />
                    </button>
                  </th>
                  <th className="p-4 font-semibold text-slate-300">
                    <button
                      onClick={() => handleSort('entity_name')}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      Entity
                      <SortIcon field="entity_name" activeField={sortField} direction={sortDirection} />
                    </button>
                  </th>
                  <th className="p-4 font-semibold text-slate-300">
                    <button
                      onClick={() => handleSort('type')}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      Type
                      <SortIcon field="type" activeField={sortField} direction={sortDirection} />
                    </button>
                  </th>
                  <th className="p-4 font-semibold text-slate-300">Version</th>
                  <th className="p-4 font-semibold text-slate-300">Status</th>
                  <th className="p-4 font-semibold text-slate-300">Expression</th>
                  <th className="p-4 font-semibold text-slate-300">Default Dimensions</th>
                  <th className="p-4 font-semibold text-slate-300">Description</th>
                  <th className="p-4 font-semibold text-slate-300">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredAndSorted.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-slate-500 italic">
                      No metrics found
                    </td>
                  </tr>
                ) : (
                  filteredAndSorted.map((metric, metricIdx) => (
                    <tr key={metric.id || `metric-${metricIdx}-${metric.name}`} className="hover:bg-white/5 transition-colors">
                      <td className="p-4 font-bold text-white">{metric.name}</td>
                      <td className="p-4 text-slate-400 font-mono text-sm">
                        {metric.entity_name || '—'}
                      </td>
                      <td className="p-4">
                        <span className="px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 text-xs font-mono">
                          {metric.type}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400 font-mono text-sm">
                        {metric.version ?? '1.0'}
                      </td>
                      <td className="p-4">
                        <StatusBadge status={metric.status ?? 'active'} />
                      </td>
                      <td className="p-4 text-slate-400 font-mono text-xs max-w-xs">
                        {truncate(metric.expression)}
                      </td>
                      <td className="p-4">
                        <div className="flex gap-1 flex-wrap">
                          {(Array.isArray(metric.default_dimensions) ? metric.default_dimensions : [])
                            .filter(dim => dim != null && dim !== '')
                            .slice(0, 2)
                            .map((dim, idx) => (
                            <span
                              key={`${metric.id || metricIdx}-${dim}-${idx}`}
                              className="text-xs px-1.5 py-0.5 rounded bg-white/5 border border-white/5 text-slate-400"
                            >
                              {dim}
                            </span>
                          ))}
                          {metric.default_dimensions && metric.default_dimensions.length > 2 && (
                            <span className="text-xs text-slate-500">
                              +{metric.default_dimensions.length - 2}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-4 text-slate-400 text-sm max-w-xs relative z-0">
                        <div className="truncate" title={metric.description || '—'}>
                          {truncate(metric.description)}
                        </div>
                      </td>
                      <td className="p-4">
                        <Link
                          to={`/metrics/${metric.id || metric.name}`}
                          className="text-sm font-medium text-cyan-400 hover:underline"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
      </div>
    </>
  );
};
