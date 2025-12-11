import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useGlossaryDimension } from '../../api/glossary';
import { ArrowLeft, Box, Activity, Layers, Loader2 } from 'lucide-react';
import { DimensionTable } from '../../components/glossary/DimensionTable';

export const DimensionView: React.FC = () => {
    const { name } = useParams<{ name: string }>();
    const { data: dim, isLoading, error } = useGlossaryDimension(name || "");

    if (isLoading) return <div className="h-full flex items-center justify-center"><Loader2 className="animate-spin text-cyan-500 w-8 h-8" /></div>;
    if (error || !dim) return <div className="p-8 text-center text-slate-500">Dimension not found.</div>;

    const safeTags = Array.isArray(dim.tags) ? dim.tags.filter(t => t != null && t !== '') : [];
    const safeMetrics = Array.isArray(dim.related_metrics) ? dim.related_metrics.filter(m => m != null && m !== '') : [];

    return (
        <div className="max-w-7xl mx-auto space-y-8 pb-20 pt-6">
            <Link to="/glossary" className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
                <ArrowLeft size={16} /> Back to Glossary
            </Link>

            {/* Header */}
            <div className="space-y-4 border-b border-white/10 pb-8">
                <div className="flex items-start justify-between">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <h1 className="text-3xl font-black text-white">{dim.name}</h1>
                            <span className="px-2 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30 text-xs font-bold uppercase tracking-wider">
                                {dim.data_type}
                            </span>
                        </div>
                        <p className="text-xl text-slate-400 max-w-2xl">{dim.description || "No description provided."}</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {safeTags.map((t, idx) => (
                        <span key={t || `tag-${idx}`} className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs font-bold uppercase tracking-wider">
                            {t}
                        </span>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Content */}
                <div className="lg:col-span-2 space-y-8">

                    {/* Related Metrics */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-white">
                            <Activity className="w-5 h-5 text-violet-400" />
                            <h2 className="text-xl font-bold">Related Metrics</h2>
                        </div>
                        <div className="grid gap-3">
                            {safeMetrics.length === 0 && <p className="text-slate-500 italic">No metrics use this dimension yet.</p>}
                            {safeMetrics.map(m => (
                                <Link key={m} to={`/glossary/metric/${m}`} className="block p-4 rounded-lg bg-[#151821] border border-white/10 hover:border-violet-500/50 transition-colors group">
                                    <div className="flex items-center justify-between">
                                        <div className="font-bold text-slate-200 group-hover:text-violet-400">{m}</div>
                                        <span className="text-xs text-slate-500">View Metric →</span>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    </div>

                    {/* Usage Graph Placeholder */}
                    <div className="p-6 rounded-xl bg-[#151821] border border-white/10 flex flex-col items-center justify-center min-h-[200px] text-center space-y-2">
                        <Layers className="w-8 h-8 text-slate-600" />
                        <p className="text-slate-500 font-medium">Visualization Available in Full Graph</p>
                        <Link to="/graph" className="text-xs text-cyan-400 hover:text-cyan-300">Open Graph Explorer</Link>
                    </div>
                </div>

                {/* Sidebar */}
                <div className="space-y-8">
                    {/* Definition Panel */}
                    <div className="p-6 rounded-xl bg-[#151821] border border-white/10 space-y-4">
                        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Definition</h3>

                        <div>
                            <label className="text-xs font-bold text-slate-600 uppercase">Inferred Type</label>
                            <div className="flex items-center gap-2 mt-1 text-slate-300 font-mono text-sm">
                                <Box size={14} className="text-cyan-500" />
                                {dim.tags.includes('time') ? 'Time Dimension' :
                                    dim.tags.includes('geo') ? 'Geographical' : 'Categorical'}
                            </div>
                        </div>

                        <div>
                            <label className="text-xs font-bold text-slate-600 uppercase">Attributes</label>
                            <div className="mt-2">
                                <DimensionTable attributes={dim.attributes} />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
