import { useEffect, useState } from 'react';
import { api, endpoints } from '../../api/client';
import { Database, CheckCircle2, XCircle, AlertCircle, Search, ChevronDown, ChevronRight } from 'lucide-react';
import { Loader2 } from 'lucide-react';

interface PromotionResult {
    id?: number;
    name: string;
    path: string;
    type?: string;
    source?: string;
    status: 'promoted' | 'ignored' | 'error';
    reason?: string;
    matched_rule?: string;
    error_message?: string;
    entity_created?: boolean;
    dimensions_count?: number;
    metrics_count?: number;
    scanned_at?: string;
}

interface PromotionDashboardData {
    counts: {
        total_scanned: number;
        promoted: number;
        ignored: number;
        errors: number;
    };
    extraction_mode: string;
    promoted: PromotionResult[];
    ignored: PromotionResult[];
    errors: PromotionResult[];
    warnings?: Array<{
        type: string;
        message: string;
        help?: string;
    }>;
}

export const PromotionDashboard = () => {
    const [data, setData] = useState<PromotionDashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'promoted' | 'ignored' | 'errors'>('promoted');
    const [searchQuery, setSearchQuery] = useState('');
    const [sourceFilter, setSourceFilter] = useState<string>('all');
    const [reasonFilter, setReasonFilter] = useState<string>('all');
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const response = await api.get(endpoints.promotion);
                setData(response.data);
                setError(null);
            } catch (err: any) {
                setError(err.message || 'Failed to load promotion data');
                console.error('Failed to load promotion data:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const toggleRow = (name: string) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(name)) {
            newExpanded.delete(name);
        } else {
            newExpanded.add(name);
        }
        setExpandedRows(newExpanded);
    };

    const getFilteredResults = (results: PromotionResult[]) => {
        return results.filter(r => {
            // Search filter
            if (searchQuery && !r.name.toLowerCase().includes(searchQuery.toLowerCase()) && 
                !r.path.toLowerCase().includes(searchQuery.toLowerCase())) {
                return false;
            }
            // Source filter
            if (sourceFilter !== 'all' && r.source !== sourceFilter) {
                return false;
            }
            // Reason filter
            if (reasonFilter !== 'all' && r.reason !== reasonFilter) {
                return false;
            }
            return true;
        });
    };

    const getActiveResults = () => {
        if (!data) return [];
        switch (activeTab) {
            case 'promoted':
                return getFilteredResults(data.promoted);
            case 'ignored':
                return getFilteredResults(data.ignored);
            case 'errors':
                return getFilteredResults(data.errors);
            default:
                return [];
        }
    };

    const getUniqueReasons = (results: PromotionResult[]) => {
        const reasons = new Set(results.map(r => r.reason).filter(Boolean));
        return Array.from(reasons).sort();
    };

    const getUniqueSources = (results: PromotionResult[]) => {
        const sources = new Set(results.map(r => r.source).filter(Boolean));
        return Array.from(sources).sort();
    };

    if (loading) {
        return (
            <div className="p-8 max-w-7xl mx-auto">
                <div className="flex items-center justify-center h-64">
                    <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
                    <span className="ml-3 text-slate-400">Loading promotion data...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-8 max-w-7xl mx-auto">
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6">
                    <div className="flex items-center gap-3">
                        <AlertCircle className="text-red-400 w-6 h-6" />
                        <div>
                            <h3 className="text-red-400 font-semibold">Failed to Load Promotion Data</h3>
                            <p className="text-slate-400 text-sm mt-1">{error}</p>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (!data) {
        return null;
    }

    const allResults = [...data.promoted, ...data.ignored, ...data.errors];
    const uniqueReasons = getUniqueReasons(allResults);
    const uniqueSources = getUniqueSources(allResults);

    return (
        <div className="p-8 max-w-7xl mx-auto">
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-white mb-2">Promotion Dashboard</h2>
                <p className="text-slate-400 text-sm">
                    Overview of models and tables scanned, promoted, and ignored during extraction
                </p>
            </div>

            {/* Warnings */}
            {data.warnings && data.warnings.length > 0 && (
                <div className="mb-6 space-y-3">
                    {data.warnings.map((warning, idx) => (
                        <div key={idx} className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
                            <div className="flex items-start gap-3">
                                <AlertCircle className="text-yellow-400 w-5 h-5 mt-0.5 flex-shrink-0" />
                                <div className="flex-1">
                                    <p className="text-yellow-400 font-semibold text-sm">{warning.message}</p>
                                    {warning.help && (
                                        <p className="text-slate-400 text-xs mt-1">{warning.help}</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div className="bg-[#151821] border border-white/10 rounded-lg p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Total Scanned</p>
                            <p className="text-2xl font-bold text-white mt-1">{data.counts.total_scanned}</p>
                        </div>
                        <div className="p-3 bg-blue-500/10 rounded-full">
                            <Database className="text-blue-400 w-6 h-6" />
                        </div>
                    </div>
                </div>
                <div className="bg-[#151821] border border-white/10 rounded-lg p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Promoted</p>
                            <p className="text-2xl font-bold text-green-400 mt-1">{data.counts.promoted}</p>
                        </div>
                        <div className="p-3 bg-green-500/10 rounded-full">
                            <CheckCircle2 className="text-green-400 w-6 h-6" />
                        </div>
                    </div>
                </div>
                <div className="bg-[#151821] border border-white/10 rounded-lg p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Ignored</p>
                            <p className="text-2xl font-bold text-slate-400 mt-1">{data.counts.ignored}</p>
                        </div>
                        <div className="p-3 bg-slate-500/10 rounded-full">
                            <XCircle className="text-slate-400 w-6 h-6" />
                        </div>
                    </div>
                </div>
                <div className="bg-[#151821] border border-white/10 rounded-lg p-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm text-slate-400">Errors</p>
                            <p className="text-2xl font-bold text-red-400 mt-1">{data.counts.errors}</p>
                        </div>
                        <div className="p-3 bg-red-500/10 rounded-full">
                            <AlertCircle className="text-red-400 w-6 h-6" />
                        </div>
                    </div>
                </div>
            </div>

            {/* Filters */}
            <div className="bg-[#151821] border border-white/10 rounded-lg p-4 mb-6">
                <div className="flex flex-wrap gap-4 items-center">
                    <div className="flex-1 min-w-[200px]">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-4 h-4" />
                            <input
                                type="text"
                                placeholder="Search by name or path..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full pl-10 pr-4 py-2 bg-background border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                            />
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <select
                            value={sourceFilter}
                            onChange={(e) => setSourceFilter(e.target.value)}
                            className="px-4 py-2 bg-background border border-white/10 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                        >
                            <option value="all">All Sources</option>
                            {uniqueSources.map(source => (
                                <option key={source} value={source}>{source}</option>
                            ))}
                        </select>
                        <select
                            value={reasonFilter}
                            onChange={(e) => setReasonFilter(e.target.value)}
                            className="px-4 py-2 bg-background border border-white/10 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                        >
                            <option value="all">All Reasons</option>
                            {uniqueReasons.map(reason => (
                                <option key={reason} value={reason}>{reason}</option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-white/10 mb-6">
                <div className="flex gap-6">
                    <button
                        onClick={() => setActiveTab('promoted')}
                        className={`pb-3 px-1 font-medium transition-colors ${
                            activeTab === 'promoted'
                                ? 'text-cyan-400 border-b-2 border-cyan-400'
                                : 'text-slate-400 hover:text-white'
                        }`}
                    >
                        Promoted ({data.counts.promoted})
                    </button>
                    <button
                        onClick={() => setActiveTab('ignored')}
                        className={`pb-3 px-1 font-medium transition-colors ${
                            activeTab === 'ignored'
                                ? 'text-cyan-400 border-b-2 border-cyan-400'
                                : 'text-slate-400 hover:text-white'
                        }`}
                    >
                        Ignored ({data.counts.ignored})
                    </button>
                    <button
                        onClick={() => setActiveTab('errors')}
                        className={`pb-3 px-1 font-medium transition-colors ${
                            activeTab === 'errors'
                                ? 'text-cyan-400 border-b-2 border-cyan-400'
                                : 'text-slate-400 hover:text-white'
                        }`}
                    >
                        Errors ({data.counts.errors})
                    </button>
                </div>
            </div>

            {/* Results Table */}
            <div className="bg-[#151821] border border-white/10 rounded-lg overflow-hidden">
                {getActiveResults().length === 0 ? (
                    <div className="p-12 text-center">
                        <p className="text-slate-400">No {activeTab} items found</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-background border-b border-white/10">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase w-8"></th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Name</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Path</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Type</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Reason</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Dimensions</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Metrics</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Entity</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {getActiveResults().map((result) => (
                                    <>
                                        <tr
                                            key={result.name}
                                            className="hover:bg-white/5 cursor-pointer"
                                            onClick={() => toggleRow(result.name)}
                                        >
                                            <td className="px-4 py-3">
                                                {expandedRows.has(result.name) ? (
                                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                                ) : (
                                                    <ChevronRight className="w-4 h-4 text-slate-400" />
                                                )}
                                            </td>
                                            <td className="px-4 py-3">
                                                <div className="font-medium text-white">{result.name}</div>
                                                {result.source && (
                                                    <div className="text-xs text-slate-500 mt-0.5">
                                                        [{result.source}]
                                                    </div>
                                                )}
                                            </td>
                                            <td className="px-4 py-3">
                                                <code className="text-xs text-slate-400 font-mono">{result.path}</code>
                                            </td>
                                            <td className="px-4 py-3">
                                                <span className="text-xs text-slate-400">{result.type || 'model'}</span>
                                            </td>
                                            <td className="px-4 py-3">
                                                <span className="text-xs text-slate-400">{result.reason || '-'}</span>
                                            </td>
                                            <td className="px-4 py-3">
                                                <span className="text-sm text-slate-300">{result.dimensions_count || 0}</span>
                                            </td>
                                            <td className="px-4 py-3">
                                                <span className="text-sm text-slate-300">{result.metrics_count || 0}</span>
                                            </td>
                                            <td className="px-4 py-3">
                                                {result.entity_created ? (
                                                    <CheckCircle2 className="w-4 h-4 text-green-400" />
                                                ) : (
                                                    <XCircle className="w-4 h-4 text-slate-600" />
                                                )}
                                            </td>
                                        </tr>
                                        {expandedRows.has(result.name) && (
                                            <tr className="bg-background/50">
                                                <td colSpan={8} className="px-4 py-4">
                                                    <div className="space-y-3 text-sm">
                                                        <div>
                                                            <span className="text-slate-400 font-semibold">Matched Rule:</span>
                                                            <span className="text-white ml-2">{result.matched_rule || 'None'}</span>
                                                        </div>
                                                        {result.error_message && (
                                                            <div>
                                                                <span className="text-red-400 font-semibold">Error:</span>
                                                                <span className="text-red-300 ml-2">{result.error_message}</span>
                                                            </div>
                                                        )}
                                                        {result.scanned_at && (
                                                            <div>
                                                                <span className="text-slate-400 font-semibold">Scanned At:</span>
                                                                <span className="text-white ml-2">{new Date(result.scanned_at).toLocaleString()}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};
