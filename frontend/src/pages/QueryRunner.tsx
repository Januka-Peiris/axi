import { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { useSearchParams } from 'react-router-dom';
import { Terminal, Copy } from 'lucide-react';
import { DimensionSelector } from '../components/DimensionSelector';

export const QueryRunner = () => {
    const [searchParams] = useSearchParams();
    const [metric, setMetric] = useState(searchParams.get('metric') || "");
    const [dimensions, setDimensions] = useState<string[]>([]);
    const [metricsList, setMetricsList] = useState<string[]>([]);
    const [sql, setSql] = useState("");
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        api.get(endpoints.metrics).then(res => {
            if (Array.isArray(res.data)) setMetricsList(res.data.map((m: any) => m.name));
        });
    }, []);

    const handleGenerate = async () => {
        if (!metric) return;
        setLoading(true);
        try {
            const res = await api.post(endpoints.query, { metric, dimensions });
            setSql(res.data?.sql || JSON.stringify(res.data, null, 2));
        } catch (e) {
            setSql("Error generating SQL");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-8 h-full flex flex-col max-w-7xl mx-auto">
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                <Terminal className="text-accent-cyan" /> Query Runner
            </h2>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
                {/* Builder */}
                <div className="card lg:col-span-1 space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-text-secondary mb-2">Metric</label>
                        <select
                            className="input w-full"
                            value={metric}
                            onChange={e => setMetric(e.target.value)}
                        >
                            <option value="">Select Metric...</option>
                            {metricsList.map(m => (
                                <option key={m} value={m}>{m}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-text-secondary mb-2">Dimensions</label>
                        <DimensionSelector
                            metric={metric || null}
                            selectedDims={dimensions}
                            onChange={setDimensions}
                        />
                    </div>

                    <button
                        onClick={handleGenerate}
                        disabled={!metric || loading}
                        className="btn btn-primary w-full disabled:opacity-50"
                    >
                        {loading ? 'Generating...' : 'Generate SQL'}
                    </button>
                </div>

                {/* Results/SQL */}
                <div className="card lg:col-span-2 flex flex-col">
                    <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
                        <div className="flex gap-4">
                            <button className="text-accent-cyan font-medium border-b-2 border-accent-cyan pb-4 -mb-4.5">SQL</button>
                            <button className="text-text-secondary font-medium pb-4">Results</button>
                        </div>
                        <button className="text-text-secondary hover:text-text-primary"><Copy size={16} /></button>
                    </div>

                    <div className="flex-1 bg-background rounded p-4 font-mono text-sm overflow-auto whitespace-pre">
                        {sql || "-- Generated SQL will appear here"}
                    </div>
                </div>
            </div>
        </div>
    );
};
