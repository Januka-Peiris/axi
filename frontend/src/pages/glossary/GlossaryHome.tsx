import React from 'react';
import { useGlossaryStats, useGlossaryEntities, useGlossaryMetrics } from '../../api/glossary';
import { GlossarySearchBar } from '../../components/glossary/GlossarySearchBar';
import { GlossaryCard } from '../../components/glossary/GlossaryCard';
import { Loader2, Activity, Box } from 'lucide-react';
import { Link } from 'react-router-dom';

export const GlossaryHome: React.FC = () => {
    const { data: stats } = useGlossaryStats();
    const { data: entities, isLoading: entLoading } = useGlossaryEntities();
    const { data: metrics, isLoading: metLoading } = useGlossaryMetrics();

    if (entLoading || metLoading) {
        return <div className="h-full flex items-center justify-center"><Loader2 className="animate-spin text-cyan-500 w-8 h-8" /></div>;
    }

    return (
        <div className="max-w-7xl mx-auto space-y-12">
            {/* Header + Search */}
            <div className="text-center space-y-6 pt-10">
                <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-violet-400">
                    Business Glossary
                </h1>
                <p className="text-slate-400 max-w-xl mx-auto">
                    Explore the definitions, logic, and relationships defining your business data.
                </p>
                <GlossarySearchBar />
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-[#151821] border border-white/5 text-center">
                    <div className="text-2xl font-bold text-white mb-1">{stats?.counts?.entities || 0}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Entities</div>
                </div>
                <div className="p-4 rounded-xl bg-[#151821] border border-white/5 text-center">
                    <div className="text-2xl font-bold text-white mb-1">{stats?.counts?.metrics || 0}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Metrics</div>
                </div>
                <div className="p-4 rounded-xl bg-[#151821] border border-white/5 text-center">
                    <div className="text-2xl font-bold text-white mb-1">{stats?.counts?.dimensions || 0}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Dimensions</div>
                </div>
                <div className="p-4 rounded-xl bg-[#151821] border border-white/5 text-center">
                    <div className="text-2xl font-bold text-white mb-1">{stats?.counts?.relationships || 0}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Relationships</div>
                </div>
            </div>

            {/* Entities Section */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-white">
                        <Box className="w-5 h-5 text-cyan-400" />
                        <h2 className="text-xl font-bold">Entities</h2>
                    </div>
                    <Link to="/glossary/entities" className="text-sm text-cyan-400 hover:text-cyan-300">View All →</Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {(Array.isArray(entities) ? entities : []).slice(0, 6).map(e => (
                        <GlossaryCard
                            key={e.name}
                            title={e.name}
                            subtitle={`${e.attributes.length} attributes`}
                            tags={e.tags}
                            linkTo={`/glossary/entity/${e.name}`}
                            accentColor="cyan"
                        >
                            {e.description}
                        </GlossaryCard>
                    ))}
                </div>
            </div>

            {/* Metrics Section */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-white">
                        <Activity className="w-5 h-5 text-violet-400" />
                        <h2 className="text-xl font-bold">Metrics</h2>
                    </div>
                    {/* Link to metrics list page if exists */}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {(Array.isArray(metrics) ? metrics : []).slice(0, 6).map(m => (
                        <GlossaryCard
                            key={m.name}
                            title={m.name}
                            subtitle={`Type: ${m.metric_type}`}
                            tags={m.tags}
                            linkTo={`/glossary/metric/${m.name}`}
                            accentColor="violet"
                        >
                            {m.description}
                        </GlossaryCard>
                    ))}
                </div>
            </div>
        </div>
    );
};
