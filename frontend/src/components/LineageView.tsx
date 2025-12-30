import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Loader2, ArrowRight, Database, BarChart3, Layers, AlertCircle } from 'lucide-react';

interface LineageNode {
    id: string;
    name: string;
    type: 'metric' | 'entity' | 'model' | 'dimension';
    level: number;
}

interface LineageViewProps {
    metricName: string;
}

const NodeIcon = ({ type }: { type: string }) => {
    switch (type) {
        case 'metric':
            return <BarChart3 className="w-4 h-4" />;
        case 'entity':
            return <Database className="w-4 h-4" />;
        case 'dimension':
            return <Layers className="w-4 h-4" />;
        default:
            return <Database className="w-4 h-4" />;
    }
};

const nodeColors: Record<string, string> = {
    metric: 'bg-purple-500/20 border-purple-500/50 text-purple-300',
    entity: 'bg-blue-500/20 border-blue-500/50 text-blue-300',
    model: 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300',
    dimension: 'bg-teal-500/20 border-teal-500/50 text-teal-300',
};

export const LineageView = ({ metricName }: LineageViewProps) => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [upstream, setUpstream] = useState<LineageNode[]>([]);
    const [downstream, setDownstream] = useState<LineageNode[]>([]);
    const [currentNode, setCurrentNode] = useState<LineageNode | null>(null);

    useEffect(() => {
        const fetchLineage = async () => {
            setLoading(true);
            setError(null);

            try {
                // Fetch metric dependencies
                const response = await api.get(`/api/metrics/${encodeURIComponent(metricName)}/dependencies`);
                const data = response.data;

                // Current metric node
                setCurrentNode({
                    id: metricName,
                    name: metricName,
                    type: 'metric',
                    level: 0
                });

                // Build upstream (source tables, entities)
                const upstreamNodes: LineageNode[] = [];
                if (data.source_model) {
                    upstreamNodes.push({
                        id: `model_${data.source_model}`,
                        name: data.source_model,
                        type: 'model',
                        level: -1
                    });
                }
                if (data.entity) {
                    upstreamNodes.push({
                        id: `entity_${data.entity}`,
                        name: data.entity,
                        type: 'entity',
                        level: -1
                    });
                }
                if (data.source_tables) {
                    data.source_tables.forEach((table: string) => {
                        upstreamNodes.push({
                            id: `table_${table}`,
                            name: table,
                            type: 'model',
                            level: -2
                        });
                    });
                }
                setUpstream(upstreamNodes);

                // Build downstream (dimensions that can be used with this metric)
                const downstreamNodes: LineageNode[] = [];
                if (data.dimensions) {
                    data.dimensions.slice(0, 8).forEach((dim: string) => {
                        downstreamNodes.push({
                            id: `dim_${dim}`,
                            name: dim,
                            type: 'dimension',
                            level: 1
                        });
                    });
                }
                if (data.downstream_metrics) {
                    data.downstream_metrics.forEach((m: string) => {
                        downstreamNodes.push({
                            id: `metric_${m}`,
                            name: m,
                            type: 'metric',
                            level: 1
                        });
                    });
                }
                setDownstream(downstreamNodes);

            } catch (err: any) {
                setError(err.response?.data?.message || 'Failed to load lineage');
            } finally {
                setLoading(false);
            }
        };

        fetchLineage();
    }, [metricName]);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="animate-spin text-cyan-500 w-6 h-6 mr-2" />
                <span className="text-slate-400">Loading lineage...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center gap-2 text-yellow-400 py-8 justify-center">
                <AlertCircle className="w-5 h-5" />
                <span>{error}</span>
            </div>
        );
    }

    return (
        <div className="py-4">
            <div className="flex items-center justify-center gap-4 overflow-x-auto pb-4">
                {/* Upstream nodes */}
                {upstream.length > 0 && (
                    <>
                        <div className="flex flex-col gap-2">
                            {upstream.filter(n => n.level === -2).map(node => (
                                <div
                                    key={node.id}
                                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${nodeColors[node.type]}`}
                                >
                                    <NodeIcon type={node.type} />
                                    <span className="text-sm font-medium truncate max-w-[120px]" title={node.name}>
                                        {node.name}
                                    </span>
                                </div>
                            ))}
                        </div>

                        {upstream.some(n => n.level === -2) && (
                            <ArrowRight className="w-5 h-5 text-slate-600 flex-shrink-0" />
                        )}

                        <div className="flex flex-col gap-2">
                            {upstream.filter(n => n.level === -1).map(node => (
                                <div
                                    key={node.id}
                                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${nodeColors[node.type]}`}
                                >
                                    <NodeIcon type={node.type} />
                                    <span className="text-sm font-medium truncate max-w-[120px]" title={node.name}>
                                        {node.name}
                                    </span>
                                </div>
                            ))}
                        </div>

                        <ArrowRight className="w-5 h-5 text-slate-600 flex-shrink-0" />
                    </>
                )}

                {/* Current metric */}
                {currentNode && (
                    <div className="flex items-center gap-2 px-4 py-3 rounded-lg border-2 border-purple-500 bg-purple-500/20 text-purple-200 shadow-lg shadow-purple-500/20">
                        <BarChart3 className="w-5 h-5" />
                        <span className="font-bold">{currentNode.name}</span>
                    </div>
                )}

                {/* Downstream nodes */}
                {downstream.length > 0 && (
                    <>
                        <ArrowRight className="w-5 h-5 text-slate-600 flex-shrink-0" />

                        <div className="flex flex-col gap-2 max-h-[200px] overflow-y-auto">
                            {downstream.map(node => (
                                <div
                                    key={node.id}
                                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${nodeColors[node.type]}`}
                                >
                                    <NodeIcon type={node.type} />
                                    <span className="text-sm font-medium truncate max-w-[120px]" title={node.name}>
                                        {node.name}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>

            {/* Legend */}
            <div className="flex justify-center gap-4 mt-4 pt-4 border-t border-white/10">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <div className="w-3 h-3 rounded bg-cyan-500/30 border border-cyan-500/50" />
                    <span>Model</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <div className="w-3 h-3 rounded bg-blue-500/30 border border-blue-500/50" />
                    <span>Entity</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <div className="w-3 h-3 rounded bg-purple-500/30 border border-purple-500/50" />
                    <span>Metric</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <div className="w-3 h-3 rounded bg-teal-500/30 border border-teal-500/50" />
                    <span>Dimension</span>
                </div>
            </div>
        </div>
    );
};

export default LineageView;
