import React, { useState } from 'react';
import { useGlossaryEntities } from '../../api/glossary';
import { Loader2, Search } from 'lucide-react';
import { Link } from 'react-router-dom';

export const EntityList: React.FC = () => {
    const { data: entities, isLoading } = useGlossaryEntities();
    const [filter, setFilter] = useState("");

    if (isLoading) return <div className="p-10 flex justify-center"><Loader2 className="animate-spin text-cyan-500" /></div>;

    const filtered = entities?.filter(e => e.name.toLowerCase().includes(filter.toLowerCase()));

    return (
        <div className="max-w-6xl mx-auto space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">All Entities</h1>
                    <p className="text-slate-400">Core business objects and tables</p>
                </div>
                <div className="relative w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Filter entities..."
                        className="w-full bg-[#151821] border border-white/10 rounded-lg py-2 pl-9 pr-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                    />
                </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-white/5 border-b border-white/10">
                        <tr>
                            <th className="p-4 font-semibold text-slate-300">Name</th>
                            <th className="p-4 font-semibold text-slate-300">Model</th>
                            <th className="p-4 font-semibold text-slate-300">Attributes</th>
                            <th className="p-4 font-semibold text-slate-300">Metrics</th>
                            <th className="p-4 font-semibold text-slate-300">Tags</th>
                            <th className="p-4 font-semibold text-slate-300">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                        {filtered?.map(e => (
                            <tr key={e.name} className="hover:bg-white/5">
                                <td className="p-4 font-bold text-white">{e.name}</td>
                                <td className="p-4 text-slate-400 font-mono text-sm">{e.model}</td>
                                <td className="p-4 text-slate-400">{e.attributes.length}</td>
                                <td className="p-4 text-slate-400">{e.metrics.length}</td>
                                <td className="p-4">
                                    <div className="flex gap-1 flex-wrap">
                                        {(Array.isArray(e.tags) ? e.tags : []).filter(t => t != null && t !== '').map((t, idx) => <span key={t || `tag-${idx}`} className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/5 text-slate-400">{t}</span>)}
                                    </div>
                                </td>
                                <td className="p-4">
                                    <Link to={`/glossary/entity/${e.name}`} className="text-sm font-medium text-cyan-400 hover:underline">Open</Link>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
