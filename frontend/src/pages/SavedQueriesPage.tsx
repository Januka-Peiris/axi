import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listSavedQueries, runSavedQuery, deleteSavedQuery, type SavedQuery } from '../features/query/api/savedQueries';
import { Loader2, Play, Trash2, ExternalLink } from 'lucide-react';

export const SavedQueriesPage = () => {
  const [queries, setQueries] = useState<SavedQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [runResult, setRunResult] = useState<any | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const navigate = useNavigate();

  const fetchQueries = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listSavedQueries();
      setQueries(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load saved queries');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueries();
  }, []);

  const filtered = useMemo(() => {
    const term = search.toLowerCase();
    if (!term) return queries;
    return queries.filter((q) =>
      (q.name || '').toLowerCase().includes(term) ||
      (q.id || '').toLowerCase().includes(term) ||
      (q.entity || '').toLowerCase().includes(term) ||
      (q.tags || []).some((t) => t.toLowerCase().includes(term))
    );
  }, [queries, search]);

  const handleOpen = (q: SavedQuery) => {
    localStorage.setItem('axi_load_saved_query', JSON.stringify(q));
    navigate('/query');
  };

  const handleRun = async (q: SavedQuery) => {
    setRunLoading(true);
    setError(null);
    try {
      const res = await runSavedQuery(q.id);
      setRunResult({ query: q.id, result: res });
    } catch (err: any) {
      setError(err?.response?.data?.detail?.message || err?.message || 'Run failed');
      setRunResult(null);
    } finally {
      setRunLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    await deleteSavedQuery(id);
    fetchQueries();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-white">Saved Queries</h1>
          <p className="text-slate-400 text-sm">Reusable semantic queries stored as YAML.</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, id, tag, entity"
          className="w-full md:w-80 bg-[#151821] border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
        />
      </div>

      <div className="rounded-xl border border-white/10 bg-[#0f172a] overflow-hidden">
        <div className="grid grid-cols-12 px-4 py-2 text-xs text-slate-400 border-b border-white/5">
          <div className="col-span-3">Name</div>
          <div className="col-span-2">ID</div>
          <div className="col-span-2">Entity</div>
          <div className="col-span-2 text-center">Metrics</div>
          <div className="col-span-2 text-center">Dimensions</div>
          <div className="col-span-3 text-right pr-2">Actions</div>
        </div>
        {loading ? (
          <div className="p-6 flex items-center justify-center text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading saved queries...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-slate-400">No saved queries found.</div>
        ) : (
          filtered.map((q) => (
            <div key={q.id} className="grid grid-cols-12 px-4 py-3 text-sm text-slate-200 border-b border-white/5 hover:bg-white/5 transition">
              <div className="col-span-3">
                <div className="font-semibold">{q.name}</div>
                <div className="text-xs text-slate-500">{q.description}</div>
                <div className="flex gap-1 mt-1">
                  {(q.tags || []).map((t) => (
                    <span key={t} className="px-2 py-0.5 rounded-full bg-white/5 text-[11px] text-slate-400 border border-white/10">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
              <div className="col-span-2 font-mono text-xs text-slate-400">{q.id}</div>
              <div className="col-span-2 text-slate-300">{q.entity}</div>
              <div className="col-span-2 text-center">{q.metrics?.length || 0}</div>
              <div className="col-span-2 text-center">{q.dimensions?.length || 0}</div>
              <div className="col-span-3 flex items-center justify-end gap-2">
                <button
                  onClick={() => handleOpen(q)}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs"
                >
                  <ExternalLink className="w-4 h-4" /> Open
                </button>
                <button
                  onClick={() => handleRun(q)}
                  disabled={runLoading}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs disabled:opacity-50"
                >
                  <Play className="w-4 h-4" /> Run
                </button>
                <button
                  onClick={() => handleDelete(q.id)}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded bg-red-500/10 text-red-400 border border-red-500/20 text-xs"
                >
                  <Trash2 className="w-4 h-4" /> Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      {runResult && (
        <div className="space-y-3 rounded-xl border border-white/10 bg-[#0f172a] p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-400">Last Run</div>
              <div className="text-white font-semibold">{runResult.query}</div>
            </div>
            {runLoading && <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />}
          </div>
          <div className="overflow-auto border border-white/5 rounded">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-slate-400">
                <tr>
                  {(runResult.result.columns || []).map((c: string) => (
                    <th key={c} className="px-3 py-2 text-left">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(runResult.result.rows || []).slice(0, 10).map((row: any[], idx: number) => (
                  <tr key={idx} className="border-t border-white/5">
                    {row.map((cell: any, ci: number) => (
                      <td key={ci} className="px-3 py-2 text-slate-200">{cell as any}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default SavedQueriesPage;
