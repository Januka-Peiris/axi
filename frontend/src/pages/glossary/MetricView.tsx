import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useGlossaryMetric } from '../../api/glossary';
import { Loader2, ArrowLeft } from 'lucide-react';
import { MetricDefinitionCard } from '../../components/glossary/MetricDefinitionCard';

export const MetricView: React.FC = () => {
    const { name } = useParams<{ name: string }>();
    const { data: metric, isLoading, error } = useGlossaryMetric(name || "");

    if (isLoading) return <div className="p-10 flex justify-center"><Loader2 className="animate-spin text-cyan-500" /></div>;
    if (error || !metric) return <div className="p-10 text-center text-red-400">Metric not found</div>;

    return (
        <div className="max-w-5xl mx-auto space-y-8 pb-20">
            <Link to="/glossary" className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to Glossary
            </Link>

            <MetricDefinitionCard metric={metric} />

            <div className="grid grid-cols-2 gap-8">
                <div>
                    <h2 className="text-lg font-bold text-white mb-4">Dimensions</h2>
                    <div className="space-y-2">
                        {(Array.isArray(metric.dimensions) ? metric.dimensions : []).map(d => (
                            <div key={d} className="p-3 bg-[#151821] border border-white/10 rounded font-mono text-sm text-cyan-300">
                                {d}
                            </div>
                        ))}
                    </div>
                </div>
                <div>
                    <h2 className="text-lg font-bold text-white mb-4">Source Tables</h2>
                    <div className="space-y-2">
                        {(Array.isArray(metric.sources) ? metric.sources : []).map(s => (
                            <Link key={s} to={`/glossary/entity/${s}`} className="block p-3 bg-[#151821] border border-white/10 rounded font-mono text-sm text-slate-300 hover:text-cyan-400 hover:border-cyan-500/50 transition-colors">
                                {s}
                            </Link>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};
