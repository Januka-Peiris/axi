import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Loader2, ArrowLeftRight, X, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface Metric {
    id?: number;
    name: string;
    type: string;
    expression: string;
    description?: string;
    entity_name?: string;
    grain?: string[];
}

interface ComparisonData {
    metric: Metric;
    sample?: {
        value: number;
        comparison?: number;
        trend?: 'up' | 'down' | 'flat';
    };
}

export const MetricCompare = () => {
    const [availableMetrics, setAvailableMetrics] = useState<Metric[]>([]);
    const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
    const [comparisonData, setComparisonData] = useState<ComparisonData[]>([]);
    const [loading, setLoading] = useState(false);
    const [metricsLoading, setMetricsLoading] = useState(true);

    useEffect(() => {
        api.get('/api/metrics')
            .then(res => {
                setAvailableMetrics(Array.isArray(res.data) ? res.data : []);
            })
            .catch(console.error)
            .finally(() => setMetricsLoading(false));
    }, []);

    useEffect(() => {
        if (selectedMetrics.length === 0) {
            setComparisonData([]);
            return;
        }

        const fetchComparisonData = async () => {
            setLoading(true);
            const data: ComparisonData[] = [];

            for (const metricName of selectedMetrics) {
                try {
                    const metricRes = await api.get(`/api/metrics/${encodeURIComponent(metricName)}`);
                    const metric = metricRes.data;

                    // Try to get a sample value
                    let sample;
                    try {
                        const sampleRes = await api.get(`/api/metrics/${encodeURIComponent(metricName)}/sample?limit=1`);
                        if (sampleRes.data?.rows?.[0]) {
                            const row = sampleRes.data.rows[0];
                            const value = Object.values(row).find(v => typeof v === 'number') as number;
                            sample = { value, trend: 'flat' as const };
                        }
                    } catch {
                        // Sample not available
                    }

                    data.push({ metric, sample });
                } catch (err) {
                    console.error(`Failed to fetch ${metricName}:`, err);
                }
            }

            setComparisonData(data);
            setLoading(false);
        };

        fetchComparisonData();
    }, [selectedMetrics]);

    const addMetric = (name: string) => {
        if (!selectedMetrics.includes(name) && selectedMetrics.length < 4) {
            setSelectedMetrics([...selectedMetrics, name]);
        }
    };

    const removeMetric = (name: string) => {
        setSelectedMetrics(selectedMetrics.filter(m => m !== name));
    };

    const TrendIcon = ({ trend }: { trend?: string }) => {
        switch (trend) {
            case 'up':
                return <TrendingUp className="w-4 h-4 text-green-400" />;
            case 'down':
                return <TrendingDown className="w-4 h-4 text-red-400" />;
            default:
                return <Minus className="w-4 h-4 text-slate-400" />;
        }
    };

    return (
        <div className="p-8 max-w-7xl mx-auto">
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-white mb-2">Compare Metrics</h1>
                <p className="text-slate-400">Side-by-side comparison of metric definitions and values</p>
            </div>

            {/* Metric Selector */}
            <div className="card mb-8">
                <h2 className="text-lg font-semibold mb-4">Select Metrics to Compare (max 4)</h2>

                {metricsLoading ? (
                    <div className="flex items-center gap-2 text-slate-400">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Loading metrics...
                    </div>
                ) : (
                    <div className="flex flex-wrap gap-2">
                        {availableMetrics.map(metric => (
                            <button
                                key={metric.name}
                                onClick={() =>
                                    selectedMetrics.includes(metric.name)
                                        ? removeMetric(metric.name)
                                        : addMetric(metric.name)
                                }
                                disabled={!selectedMetrics.includes(metric.name) && selectedMetrics.length >= 4}
                                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                    selectedMetrics.includes(metric.name)
                                        ? 'bg-cyan-500 text-white'
                                        : 'bg-white/5 text-slate-300 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed'
                                }`}
                            >
                                {selectedMetrics.includes(metric.name) && (
                                    <X className="w-3 h-3 inline mr-1" />
                                )}
                                {metric.name}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Comparison Table */}
            {selectedMetrics.length > 0 && (
                <div className="card overflow-hidden">
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2 className="w-6 h-6 text-cyan-500 animate-spin mr-2" />
                            Loading comparison data...
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-white/10">
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase w-40">
                                            Attribute
                                        </th>
                                        {comparisonData.map(d => (
                                            <th
                                                key={d.metric.name}
                                                className="px-4 py-3 text-left text-sm font-semibold text-white"
                                            >
                                                <div className="flex items-center gap-2">
                                                    {d.metric.name}
                                                    <button
                                                        onClick={() => removeMetric(d.metric.name)}
                                                        className="text-slate-400 hover:text-red-400"
                                                    >
                                                        <X className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {/* Type */}
                                    <tr className="hover:bg-white/5">
                                        <td className="px-4 py-3 text-sm text-slate-400 font-medium">Type</td>
                                        {comparisonData.map(d => (
                                            <td key={d.metric.name} className="px-4 py-3">
                                                <span className="px-2 py-1 rounded bg-purple-500/20 text-purple-300 text-xs font-medium">
                                                    {d.metric.type}
                                                </span>
                                            </td>
                                        ))}
                                    </tr>

                                    {/* Entity */}
                                    <tr className="hover:bg-white/5">
                                        <td className="px-4 py-3 text-sm text-slate-400 font-medium">Entity</td>
                                        {comparisonData.map(d => (
                                            <td key={d.metric.name} className="px-4 py-3 text-sm text-slate-300">
                                                {d.metric.entity_name || <span className="text-slate-600">-</span>}
                                            </td>
                                        ))}
                                    </tr>

                                    {/* Expression */}
                                    <tr className="hover:bg-white/5">
                                        <td className="px-4 py-3 text-sm text-slate-400 font-medium">Expression</td>
                                        {comparisonData.map(d => (
                                            <td key={d.metric.name} className="px-4 py-3">
                                                <code className="text-xs text-cyan-400 bg-black/30 px-2 py-1 rounded font-mono">
                                                    {d.metric.expression}
                                                </code>
                                            </td>
                                        ))}
                                    </tr>

                                    {/* Grain */}
                                    <tr className="hover:bg-white/5">
                                        <td className="px-4 py-3 text-sm text-slate-400 font-medium">Grain</td>
                                        {comparisonData.map(d => (
                                            <td key={d.metric.name} className="px-4 py-3 text-sm text-slate-300">
                                                {d.metric.grain?.join(', ') || <span className="text-slate-600">-</span>}
                                            </td>
                                        ))}
                                    </tr>

                                    {/* Description */}
                                    <tr className="hover:bg-white/5">
                                        <td className="px-4 py-3 text-sm text-slate-400 font-medium">Description</td>
                                        {comparisonData.map(d => (
                                            <td key={d.metric.name} className="px-4 py-3 text-sm text-slate-300 max-w-xs">
                                                {d.metric.description || <span className="text-slate-600 italic">No description</span>}
                                            </td>
                                        ))}
                                    </tr>

                                    {/* Sample Value */}
                                    <tr className="hover:bg-white/5 bg-cyan-500/5">
                                        <td className="px-4 py-3 text-sm text-slate-400 font-medium">Sample Value</td>
                                        {comparisonData.map(d => (
                                            <td key={d.metric.name} className="px-4 py-3">
                                                {d.sample ? (
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-lg font-bold text-white">
                                                            {d.sample.value?.toLocaleString() ?? '-'}
                                                        </span>
                                                        <TrendIcon trend={d.sample.trend} />
                                                    </div>
                                                ) : (
                                                    <span className="text-slate-600 italic">No data</span>
                                                )}
                                            </td>
                                        ))}
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

            {selectedMetrics.length === 0 && (
                <div className="card text-center py-16">
                    <ArrowLeftRight className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                    <p className="text-slate-400">Select metrics above to compare them side-by-side</p>
                </div>
            )}
        </div>
    );
};

export default MetricCompare;
