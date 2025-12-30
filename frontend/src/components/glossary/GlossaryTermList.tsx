import { BookOpen } from 'lucide-react';
import { useGlossaryTerms } from '../../api/glossary';

interface Props {
    linkedMetric?: string;
    linkedEntity?: string;
}

export const GlossaryTermList: React.FC<Props> = ({ linkedMetric, linkedEntity }) => {
    const { data: terms, isLoading, error } = useGlossaryTerms({
        linked_metric: linkedMetric,
        linked_entity: linkedEntity,
    });

    return (
        <div className="p-6 rounded-xl bg-[#151821] border border-white/10 space-y-3">
            <div className="flex items-center gap-2 text-white">
                <BookOpen className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                    Glossary
                </h3>
            </div>
            {isLoading && <div className="text-slate-500 text-sm">Loading terms…</div>}
            {error && <div className="text-red-400 text-sm">Failed to load terms</div>}
            {!isLoading && !error && (!terms || terms.length === 0) && (
                <div className="text-slate-500 text-sm">
                    No glossary terms linked yet.
                </div>
            )}
            <div className="space-y-3">
                {(terms || []).map(term => (
                    <div key={term.term} className="p-3 rounded-lg bg-white/5 border border-white/5">
                        <div className="flex items-center justify-between">
                            <div className="text-white font-semibold">{term.term}</div>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                                term.status === 'approved' ? 'bg-green-500/20 text-green-400' :
                                term.status === 'deprecated' ? 'bg-red-500/20 text-red-400' :
                                'bg-yellow-500/20 text-yellow-400'
                            }`}>
                                {term.status}
                            </span>
                        </div>
                        <p className="text-slate-400 text-sm mt-1">{term.definition}</p>
                        <div className="flex flex-wrap gap-2 mt-2 text-xs text-slate-500">
                            {term.scope && <span className="px-2 py-0.5 rounded bg-white/10">Scope: {term.scope}</span>}
                            {term.derived_from?.map((src) => (
                                <span key={src} className="px-2 py-0.5 rounded bg-white/10 text-cyan-300">
                                    {src}
                                </span>
                            ))}
                            {term.applies_to_entities?.map((ent) => (
                                <span key={ent} className="px-2 py-0.5 rounded bg-white/10 text-violet-300">
                                    {ent}
                                </span>
                            ))}
                            {term.synonyms?.map((syn) => (
                                <span key={syn} className="px-2 py-0.5 rounded bg-white/10 text-slate-400">
                                    {syn}
                                </span>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default GlossaryTermList;
