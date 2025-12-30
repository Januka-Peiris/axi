import React from 'react';
import { useGlossaryTerms } from '../../api/glossary';
import { GlossarySearchBar } from '../../components/glossary/GlossarySearchBar';
import { Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

export const GlossaryHome: React.FC = () => {
    const { data: terms, isLoading: termLoading } = useGlossaryTerms();

    if (termLoading) {
        return <div className="h-full flex items-center justify-center"><Loader2 className="animate-spin text-cyan-500 w-8 h-8" /></div>;
    }

    return (
        <div className="max-w-7xl mx-auto space-y-12">
            {/* Header + Search */}
            <div className="text-center space-y-4 pt-10">
                <p className="text-xs font-semibold tracking-[0.3em] text-slate-500 uppercase">Glossary</p>
                <h1 className="text-4xl font-black text-white">
                    Words we agree on
                </h1>
                <p className="text-slate-400 max-w-xl mx-auto leading-relaxed">
                    Clear definitions for the terms the business actually uses.
                </p>
                <GlossarySearchBar />
            </div>

            {/* Glossary Terms Section */}
            <div className="space-y-6">
                {(terms || []).map(t => (
                    <article
                        key={t.term}
                        className="space-y-2 border-b border-white/5 pb-6 last:border-b-0"
                    >
                        <div className="flex items-center gap-3">
                            <Link
                                to={`/glossary/term/${encodeURIComponent(t.term)}`}
                                className="text-2xl font-bold text-white hover:text-cyan-200 transition-colors"
                            >
                                {t.term}
                            </Link>
                            <span
                                className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${
                                    t.status === 'approved'
                                        ? 'bg-green-500/15 text-green-300'
                                        : t.status === 'deprecated'
                                            ? 'bg-red-500/15 text-red-300'
                                            : 'bg-yellow-500/15 text-yellow-300'
                                }`}
                            >
                                {t.status}
                            </span>
                        </div>
                        <p className="text-slate-300 leading-relaxed">{t.definition}</p>
                        {t.synonyms && t.synonyms.length > 0 && (
                            <p className="text-sm text-slate-500">
                                Synonyms: {t.synonyms.join(', ')}
                            </p>
                        )}
                    </article>
                ))}
                {(!terms || terms.length === 0) && (
                    <div className="text-slate-500 text-sm text-center">
                        This glossary is intentionally small and curated. Add terms when the business meaning matters.
                    </div>
                )}
            </div>
        </div>
    );
};
