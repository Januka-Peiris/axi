import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import type { DimensionListItem } from '../api/getDimensions';
import { Loader2 } from 'lucide-react';

interface DimensionListTableProps {
  dimensions: DimensionListItem[];
  isLoading?: boolean;
}

type SortField = 'dimension_name' | 'entity_name' | 'cardinality';
type SortDirection = 'asc' | 'desc';

export const DimensionListTable: React.FC<DimensionListTableProps> = ({
  dimensions,
  isLoading = false,
}) => {
  const [search, setSearch] = useState('');
  const [entityFilter, setEntityFilter] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('dimension_name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Get unique entities for filter
  const uniqueEntities = useMemo(() => {
    const entities = new Set<string>();
    dimensions.forEach((d) => {
      if (d.entity_name) entities.add(d.entity_name);
    });
    return Array.from(entities).sort();
  }, [dimensions]);

  // Filter and sort dimensions
  const filteredAndSorted = useMemo(() => {
    let filtered = dimensions.filter((d) => {
      const matchesSearch =
        d.dimension_name.toLowerCase().includes(search.toLowerCase()) ||
        (d.entity_name?.toLowerCase().includes(search.toLowerCase()) ?? false);
      const matchesEntity = !entityFilter || d.entity_name === entityFilter;
      return matchesSearch && matchesEntity;
    });

    // Sort
    filtered.sort((a, b) => {
      let aVal: string | number;
      let bVal: string | number;

      switch (sortField) {
        case 'dimension_name':
          aVal = a.dimension_name;
          bVal = b.dimension_name;
          break;
        case 'entity_name':
          aVal = a.entity_name || '';
          bVal = b.entity_name || '';
          break;
        case 'cardinality':
          aVal = a.cardinality ?? 0;
          bVal = b.cardinality ?? 0;
          break;
        default:
          return 0;
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      } else {
        return sortDirection === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
      }
    });

    return filtered;
  }, [dimensions, search, entityFilter, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3 h-3 text-slate-500" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-3 h-3 text-cyan-400" />
    ) : (
      <ArrowDown className="w-3 h-3 text-cyan-400" />
    );
  };

  if (isLoading) {
    return (
      <div className="p-10 flex justify-center">
        <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search dimensions or entities..."
            className="w-full bg-[#151821] border border-white/10 rounded-lg py-2 pl-9 pr-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
          className="bg-[#151821] border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
        >
          <option value="">All Entities</option>
          {uniqueEntities.map((entity) => (
            <option key={entity} value={entity}>
              {entity}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[800px]">
          <thead className="bg-white/5 border-b border-white/10">
            <tr>
              <th className="p-4 font-semibold text-slate-300 w-[200px] min-w-[150px]">
                <button
                  onClick={() => handleSort('dimension_name')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  Dimension Name
                  <SortIcon field="dimension_name" />
                </button>
              </th>
              <th className="p-4 font-semibold text-slate-300 w-[180px] min-w-[120px]">
                <button
                  onClick={() => handleSort('entity_name')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  Entity Name
                  <SortIcon field="entity_name" />
                </button>
              </th>
              <th className="p-4 font-semibold text-slate-300 w-[120px] min-w-[100px]">Data Type</th>
              <th className="p-4 font-semibold text-slate-300 w-[120px] min-w-[100px]">
                <button
                  onClick={() => handleSort('cardinality')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  Cardinality
                  <SortIcon field="cardinality" />
                </button>
              </th>
              <th className="p-4 font-semibold text-slate-300 w-[100px] min-w-[80px]">Primary Key</th>
              <th className="p-4 font-semibold text-slate-300 w-[320px] min-w-[240px]">Description</th>
              <th className="p-4 font-semibold text-slate-300 w-[110px] min-w-[90px] sticky right-0 bg-[#151821] z-20 shadow-[inset_1px_0_0_rgba(255,255,255,0.08)]">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filteredAndSorted.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-slate-500 italic">
                  No dimensions found
                </td>
              </tr>
            ) : (
              filteredAndSorted.map((dim) => (
                <tr key={dim.id} className="hover:bg-white/5 transition-colors">
                  <td className="p-4 font-bold text-white w-[200px] min-w-[150px]">
                    <div className="truncate" title={dim.dimension_name}>{dim.dimension_name}</div>
                  </td>
                  <td className="p-4 text-slate-400 font-mono text-sm w-[180px] min-w-[120px]">
                    <div className="truncate" title={dim.entity_name || '—'}>{dim.entity_name || '—'}</div>
                  </td>
                  <td className="p-4 w-[120px] min-w-[100px]">
                    <span className="px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 text-xs font-mono whitespace-nowrap">
                      {dim.data_type}
                    </span>
                  </td>
                  <td className="p-4 text-slate-400 w-[120px] min-w-[100px]">
                    {dim.cardinality !== null ? dim.cardinality.toLocaleString() : '—'}
                  </td>
                  <td className="p-4 w-[100px] min-w-[80px]">
                    {dim.is_primary ? (
                      <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs font-bold uppercase whitespace-nowrap">
                        PK
                      </span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="p-4 w-[320px] min-w-[240px]">
                    <div 
                      className="text-slate-200 text-sm leading-6 break-words whitespace-normal line-clamp-3" 
                      title={dim.description || '—'}
                    >
                      {dim.description || '—'}
                    </div>
                  </td>
                  <td className="p-4 w-[110px] min-w-[90px] sticky right-0 bg-[#151821] z-20 shadow-[inset_1px_0_0_rgba(255,255,255,0.08)]">
                    <Link
                      to={`/dimensions/${dim.id}`}
                      className="text-sm font-medium text-cyan-400 hover:underline whitespace-nowrap"
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
    </div>
  );
};
