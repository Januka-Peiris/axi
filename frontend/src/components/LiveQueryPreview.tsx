import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { Loader2, Play, Pause, RefreshCw, Table, AlertCircle, CheckCircle } from 'lucide-react';

interface LiveQueryPreviewProps {
    metrics: string[];
    dimensions: string[];
    filters?: any[];
    limit?: number;
    autoRefresh?: boolean;
    refreshInterval?: number;
    onResultsChange?: (results: any) => void;
}

interface QueryResult {
    columns: string[];
    rows: any[][];
    rowCount: number;
    executionMs: number;
}

export const LiveQueryPreview = ({
    metrics,
    dimensions,
    filters = [],
    limit = 10,
    autoRefresh = false,
    refreshInterval = 5000,
    onResultsChange
}: LiveQueryPreviewProps) => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<QueryResult | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [isAutoRefreshing, setIsAutoRefreshing] = useState(autoRefresh);

    const executeQuery = useCallback(async () => {
        if (metrics.length === 0) {
            setResult(null);
            setError(null);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await api.post('/api/query/semantic', {
                metrics,
                dimensions,
                filters,
                limit
            });

            const data = response.data;

            if (data.error) {
                setError(data.error.message || 'Query failed');
                setResult(null);
            } else {
                const queryResult: QueryResult = {
                    columns: data.columns || [],
                    rows: data.rows || [],
                    rowCount: data.rows?.length || 0,
                    executionMs: data.execution_ms || 0
                };
                setResult(queryResult);
                setLastUpdated(new Date());
                onResultsChange?.(queryResult);
            }
        } catch (err: any) {
            const message = err.response?.data?.detail?.message || err.message || 'Query failed';
            setError(message);
            setResult(null);
        } finally {
            setLoading(false);
        }
    }, [metrics, dimensions, filters, limit, onResultsChange]);

    // Auto-execute when inputs change
    useEffect(() => {
        const debounceTimer = setTimeout(() => {
            if (metrics.length > 0) {
                executeQuery();
            }
        }, 500);

        return () => clearTimeout(debounceTimer);
    }, [metrics, dimensions, filters, limit]);

    // Auto-refresh interval
    useEffect(() => {
        if (!isAutoRefreshing || metrics.length === 0) return;

        const interval = setInterval(executeQuery, refreshInterval);
        return () => clearInterval(interval);
    }, [isAutoRefreshing, refreshInterval, executeQuery, metrics.length]);

    const formatValue = (value: any) => {
        if (value === null || value === undefined) {
            return <span className="text-slate-600 italic">null</span>;
        }
        if (typeof value === 'number') {
            return <span className="text-orange-400">{value.toLocaleString()}</span>;
        }
        if (typeof value === 'boolean') {
            return <span className="text-purple-400">{value.toString()}</span>;
        }
        return <span className="text-slate-300">{String(value)}</span>;
    };

    if (metrics.length === 0) {
        return (
            <div className="rounded-xl border border-white/10 bg-[#151821] p-8">
                <div className="text-center text-slate-500">
                    <Table className="w-8 h-8 mx-auto mb-3 opacity-50" />
                    <p>Select metrics to see live preview</p>
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#0d0f15]">
                <div className="flex items-center gap-3">
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                        Live Preview
                    </h3>
                    {loading && (
                        <Loader2 className="w-4 h-4 text-cyan-500 animate-spin" />
                    )}
                    {!loading && result && (
                        <span className="flex items-center gap-1 text-xs text-green-400">
                            <CheckCircle className="w-3 h-3" />
                            {result.rowCount} rows in {result.executionMs.toFixed(0)}ms
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {lastUpdated && (
                        <span className="text-xs text-slate-500">
                            Updated {lastUpdated.toLocaleTimeString()}
                        </span>
                    )}
                    <button
                        onClick={() => setIsAutoRefreshing(!isAutoRefreshing)}
                        className={`p-1.5 rounded transition-colors ${
                            isAutoRefreshing
                                ? 'bg-cyan-500/20 text-cyan-400'
                                : 'bg-white/5 text-slate-400 hover:text-white'
                        }`}
                        title={isAutoRefreshing ? 'Stop auto-refresh' : 'Start auto-refresh'}
                    >
                        {isAutoRefreshing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    </button>
                    <button
                        onClick={executeQuery}
                        disabled={loading}
                        className="p-1.5 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white transition-colors disabled:opacity-50"
                        title="Refresh"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="p-4">
                {error && (
                    <div className="flex items-center gap-2 text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        <span className="text-sm">{error}</span>
                    </div>
                )}

                {result && result.rows.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/10">
                                    {result.columns.map((col, i) => (
                                        <th
                                            key={i}
                                            className="px-3 py-2 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider"
                                        >
                                            {col}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {result.rows.map((row, rowIdx) => (
                                    <tr key={rowIdx} className="hover:bg-white/5">
                                        {row.map((cell, cellIdx) => (
                                            <td key={cellIdx} className="px-3 py-2 font-mono text-xs">
                                                {formatValue(cell)}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : result ? (
                    <div className="text-center text-slate-500 py-8">
                        <Table className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>No results returned</p>
                    </div>
                ) : !loading && !error ? (
                    <div className="text-center text-slate-500 py-8">
                        <Loader2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>Waiting for query...</p>
                    </div>
                ) : null}
            </div>
        </div>
    );
};

export default LiveQueryPreview;
