import React, { useState, useEffect } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { useGlossarySearch } from '../../api/glossary';
import { Link } from 'react-router-dom';
import { clsx } from 'clsx';

export const GlossarySearchBar: React.FC = () => {
    const [query, setQuery] = useState("");
    const [showResults, setShowResults] = useState(false);
    const { data: results, isLoading } = useGlossarySearch(query);

    // Debounce handled by query hook usually, but let's just rely on simple handling for now
    // or add debounce if needed. For now direct state.

    useEffect(() => {
        if (query.length > 1) setShowResults(true);
        else setShowResults(false);
    }, [query]);

    // Close on click outside (simplified)

    return (
        <div className="relative w-full max-w-2xl mx-auto z-50">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                <input
                    type="text"
                    className="w-full bg-[#0d0f15] border border-white/10 rounded-lg py-3 pl-10 pr-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all"
                    placeholder="Search entities, metrics, dimensions..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onFocus={() => query.length > 1 && setShowResults(true)}
                    onBlur={() => setTimeout(() => setShowResults(false), 200)} // delay to allow click
                />
                {isLoading && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyan-500 animate-spin" />}
            </div>

            {showResults && (Array.isArray(results) ? results : []).length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-[#151821] border border-white/10 rounded-lg shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    <div className="p-2">
                        {(Array.isArray(results) ? results : []).slice(0, 8).map((r, i) => (
                            <Link
                                key={i}
                                to={r.type === 'entity' ? `/glossary/entity/${r.name}` : `/glossary/metric/${r.name}`}
                                className="flex items-center justify-between p-3 hover:bg-white/5 rounded-md group transition-colors"
                            >
                                <div className="flex flex-col">
                                    <span className="text-sm font-medium text-slate-200 group-hover:text-cyan-400 transition-colors">{r.name}</span>
                                    {r.description && <span className="text-xs text-slate-500 line-clamp-1">{r.description}</span>}
                                </div>
                                <span className={clsx(
                                    "text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded border",
                                    r.type === 'entity' ? "border-cyan-500/30 text-cyan-400 bg-cyan-500/10" : "border-violet-500/30 text-violet-400 bg-violet-500/10"
                                )}>
                                    {r.type}
                                </span>
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
