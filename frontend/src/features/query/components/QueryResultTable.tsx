import React, { useState, useMemo } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown, Loader2 } from 'lucide-react';

interface QueryResultTableProps {
  columns: string[];
  rows: any[];
  isLoading?: boolean;
  error?: string | null;
}

type SortDirection = 'asc' | 'desc';

export const QueryResultTable: React.FC<QueryResultTableProps> = ({
  columns,
  rows,
  isLoading = false,
  error = null,
}) => {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  const sortedRows = useMemo(() => {
    if (!sortColumn) return rows;
    const colIndex = columns.indexOf(sortColumn);

    return [...rows].sort((a, b) => {
      const aVal = Array.isArray(a) && colIndex >= 0 ? a[colIndex] : (a as any)[sortColumn];
      const bVal = Array.isArray(b) && colIndex >= 0 ? b[colIndex] : (b as any)[sortColumn];

      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
      }

      const aStr = String(aVal);
      const bStr = String(bVal);
      return sortDirection === 'asc'
        ? aStr.localeCompare(bStr)
        : bStr.localeCompare(aStr);
    });
  }, [rows, sortColumn, sortDirection, columns]);

  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, currentPage]);

  const totalPages = Math.ceil(sortedRows.length / pageSize);

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
    // Reset to first page when sorting changes
    setCurrentPage(1);
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortColumn !== column) {
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
      <div className="rounded-xl border border-white/10 bg-[#151821] p-10 flex justify-center">
        <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6">
        <div className="text-red-400 font-medium">Error</div>
        <div className="text-red-300 text-sm mt-2">{error}</div>
      </div>
    );
  }

  if (columns.length === 0 || rows.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-[#151821] p-8 text-center text-slate-500">
        No results to display. Run a query to see results.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
          Results ({rows.length} rows)
        </h3>
        {totalPages > 1 && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-2 py-1 rounded border border-white/10 hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span>
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-2 py-1 rounded border border-white/10 hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-white/5 border-b border-white/10">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="p-3 font-semibold text-slate-300 cursor-pointer hover:bg-white/5"
                  onClick={() => handleSort(col)}
                >
                  <div className="flex items-center gap-2">
                    {col}
                    <SortIcon column={col} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {paginatedRows.map((row, idx) => (
              <tr key={idx} className="hover:bg-white/5 transition-colors">
                {columns.map((col, cIdx) => {
                  const val = Array.isArray(row) ? row[cIdx] : row[col];
                  return (
                    <td key={col} className="p-3 text-slate-300 font-mono text-sm">
                      {val !== null && val !== undefined ? String(val) : '—'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
