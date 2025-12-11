import { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { Database } from 'lucide-react';

export const Models = () => {
    const [models, setModels] = useState<any[]>([]);
    const [search, setSearch] = useState("");

    useEffect(() => {
        api.get(endpoints.models).then(res => {
            if (Array.isArray(res.data)) {
                // Handle both string array and object array formats
                const modelData = res.data.map((item: any) => {
                    if (typeof item === 'string') {
                        return { name: item };
                    }
                    return item;
                });
                setModels(modelData);
            }
        }).catch(err => {
            console.error('Failed to load models:', err);
            setModels([]);
        });
    }, []);

    const filtered = models.filter(m => m && m.name && m.name.toLowerCase().includes(search.toLowerCase()));

    return (
        <div className="p-8 max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    <Database className="text-accent-violet" /> Models
                </h2>
                <input
                    type="text"
                    placeholder="Search models..."
                    className="input w-64"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                />
            </div>

            <div className="grid gap-4">
                {filtered.map(m => (
                    <div key={m.name} className="card hover:bg-panel/80 transition-colors cursor-pointer">
                        <div className="flex items-center justify-between gap-4">
                            <div className="flex-1 min-w-0">
                                <h3 className="text-lg font-semibold text-text-primary truncate">{m.name}</h3>
                                <div className="flex gap-2 mt-2 flex-wrap max-w-full">
                                    {(Array.isArray(m.dimensions) ? m.dimensions : []).slice(0, 5).map((d: string) => (
                                        <span key={d} className="badge bg-background text-text-secondary border border-border text-xs whitespace-nowrap">{d}</span>
                                    ))}
                                    {(Array.isArray(m.dimensions) ? m.dimensions : []).length > 5 && (
                                        <span className="badge bg-background text-text-secondary border border-border text-xs">
                                            +{(Array.isArray(m.dimensions) ? m.dimensions : []).length - 5} more
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="text-text-secondary text-sm">
                                {m.type || 'table'}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
