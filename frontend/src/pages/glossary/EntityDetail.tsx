import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useGlossaryEntity } from '../../api/glossary';
import { Loader2, ArrowLeft } from 'lucide-react';
import { EntityAttributeTable } from '../../components/glossary/EntityAttributeTable';
import { RelationshipGraph } from '../../components/glossary/RelationshipGraph';
import { LocalSubgraph } from '../../components/graph/LocalSubgraph';

export const EntityDetail: React.FC = () => {
    const { name } = useParams<{ name: string }>();
    const { data: entity, isLoading, error } = useGlossaryEntity(name || "");

    if (isLoading) return <div className="p-10 flex justify-center"><Loader2 className="animate-spin text-cyan-500" /></div>;
    if (error || !entity) return <div className="p-10 text-center text-red-400">Entity not found</div>;

    return (
        <div className="max-w-7xl mx-auto space-y-8 pb-20">
            <Link to="/glossary/entities" className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to Entities
            </Link>

            {/* Header */}
            <div>
                <div className="flex items-center gap-4 mb-2">
                    <h1 className="text-3xl font-black text-white">{entity.name}</h1>
                    <div className="flex gap-2">
                        {(Array.isArray(entity.tags) ? entity.tags : []).filter(t => t != null && t !== '').map((t, idx) => (
                            <span key={t || `tag-${idx}`} className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs font-bold uppercase tracking-wider">
                                {t}
                            </span>
                        ))}
                    </div>
                </div>
                <p className="text-lg text-slate-400">{entity.description}</p>
            </div>

            {/* Stats Check */}
            <div className="grid grid-cols-4 gap-4 p-4 rounded-xl bg-[#151821] border border-white/5">
                <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Model</div>
                    <div className="font-mono text-white">{entity.model}</div>
                </div>
                <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Attributes</div>
                    <div className="font-mono text-white">{entity.attributes.length}</div>
                </div>
                <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Relationships</div>
                    <div className="font-mono text-white">{entity.relationships.length}</div>
                </div>
            </div>

            {/* Local Subgraph */}
            <div className="space-y-4">
                <h2 className="text-xl font-bold text-white">Graph View</h2>
                <LocalSubgraph 
                    nodeId={entity.name} 
                    depth={1}
                    height="400px"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Content */}
                <div className="lg:col-span-2 space-y-8">
                    <div>
                        <h2 className="text-xl font-bold text-white mb-4">Attributes</h2>
                        <EntityAttributeTable attributes={entity.attributes} />
                    </div>

                    <div>
                        <h2 className="text-xl font-bold text-white mb-4">Relationships</h2>
                        <RelationshipGraph entity={entity} />
                    </div>
                </div>

                {/* Sidebar */}
                <div className="space-y-8">
                    <div>
                        <h2 className="text-xl font-bold text-white mb-4">Related Metrics</h2>
                        <div className="space-y-3">
                            {entity.metrics.length === 0 && <p className="text-slate-500 italic">No metrics linked.</p>}
                            {(Array.isArray(entity.metrics) ? entity.metrics : []).map(m => (
                                <Link key={m} to={`/glossary/metric/${m}`} className="block p-4 rounded-lg bg-[#151821] border border-white/10 hover:border-violet-500/50 transition-colors group">
                                    <div className="font-bold text-slate-200 group-hover:text-violet-400">{m}</div>
                                    <div className="text-xs text-slate-500 mt-1">Click to view definition</div>
                                </Link>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
