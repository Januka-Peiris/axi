import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useGlossaryTerm } from '../../api/glossary';
import { Loader2, ArrowLeft, BookOpen } from 'lucide-react';

export const GlossaryTermView: React.FC = () => {
    const { term } = useParams<{ term: string }>();
    const { data: glossaryTerm, isLoading, error } = useGlossaryTerm(term || "");

    if (isLoading) return <div className="h-full flex items-center justify-center"><Loader2 className="animate-spin text-cyan-500 w-8 h-8" /></div>;
    if (error || !glossaryTerm) return <div className="p-8 text-center text-slate-500">Term not found.</div>;

    return (
        <div className="max-w-4xl mx-auto space-y-6 pb-20 pt-6">
            <Link to="/glossary" className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
                <ArrowLeft size={16} /> Back to Glossary
            </Link>

            <div className="p-6 rounded-xl bg-[#151821] border border-white/10 space-y-4">
                <div className="flex items-center gap-3">
                    <BookOpen className="w-6 h-6 text-cyan-400" />
                    <div>
                        <h1 className="text-3xl font-black text-white">{glossaryTerm.term}</h1>
                        <div className="flex items-center gap-2 mt-1">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                                glossaryTerm.status === 'approved' ? 'bg-green-500/20 text-green-400' :
                                glossaryTerm.status === 'deprecated' ? 'bg-red-500/20 text-red-400' :
                                'bg-yellow-500/20 text-yellow-400'
                            }`}>
                                {glossaryTerm.status}
                            </span>
                            <span className="text-xs text-slate-500">v{glossaryTerm.version}</span>
                        </div>
                    </div>
                </div>

                <div className="text-slate-300 leading-relaxed">{glossaryTerm.definition}</div>

                {glossaryTerm.scope && (
                    <div className="text-sm text-slate-400">
                        <span className="font-semibold text-white">Scope:</span> {glossaryTerm.scope}
                    </div>
                )}
                {glossaryTerm.notes && (
                    <div className="text-sm text-slate-400">
                        <span className="font-semibold text-white">Notes:</span> {glossaryTerm.notes}
                    </div>
                )}

                <div className="space-y-2">
                    {glossaryTerm.derived_from?.length > 0 && (
                        <div className="text-sm text-slate-400">
                            <span className="font-semibold text-white">Derived from:</span>{" "}
                            {glossaryTerm.derived_from.join(", ")}
                        </div>
                    )}
                    {glossaryTerm.applies_to_entities?.length > 0 && (
                        <div className="text-sm text-slate-400">
                            <span className="font-semibold text-white">Applies to entities:</span>{" "}
                            {glossaryTerm.applies_to_entities.join(", ")}
                        </div>
                    )}
                    {glossaryTerm.synonyms?.length > 0 && (
                        <div className="text-sm text-slate-400">
                            <span className="font-semibold text-white">Synonyms:</span>{" "}
                            {glossaryTerm.synonyms.join(", ")}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default GlossaryTermView;
