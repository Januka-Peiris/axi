import { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { Activity, Play } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Metrics = () => {
    const [metrics, setMetrics] = useState<any[]>([]);
    const [search, setSearch] = useState("");

    useEffect(() => {
        api.get(endpoints.metrics).then(res => {
            if (Array.isArray(res.data)) setMetrics(res.data);
        });
    }, []);

    const filtered = metrics.filter(m => m.name.toLowerCase().includes(search.toLowerCase()));

    return (
        <div className="p-8 max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    <Activity className="text-accent-aqua" /> Metrics
                </h2>
                <input
                    type="text"
                    placeholder="Search metrics..."
                    className="input w-64"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                />
            </div>

            <div className="grid gap-4">
                {filtered.map((m: any) => (
                    <div key={m.name} className="card group">
                        <div className="flex items-start justify-between">
                            <div>
                                <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                                    {m.name}
                                    <span className="badge bg-accent-cyan/10 text-accent-cyan border-none">{m.metric_type}</span>
                                </h3>
                                <code className="block mt-2 text-sm bg-background p-2 rounded text-text-secondary font-mono">
                                    {m.expression}
                                </code>
                                <div className="flex gap-2 mt-3">
                                    {(Array.isArray(m.tags) ? m.tags : []).map((t: string) => (
                                        <span key={t} className="text-xs text-text-secondary">#{t}</span>
                                    ))}
                                </div>
                            </div>

                            <Link
                                to={`/query?metric=${m.name}`}
                                className="btn btn-secondary flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <Play size={14} /> Run
                            </Link>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
