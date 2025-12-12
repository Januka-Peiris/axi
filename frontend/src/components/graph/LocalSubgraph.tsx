import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Loader2, AlertCircle } from 'lucide-react';
import { SemanticGraph } from './SemanticGraph';
import type { VisGraphNode, VisGraphEdge } from './types';

interface LocalSubgraphProps {
    nodeId: string;
    depth?: number;
    onNodeClick?: (nodeId: string, node: VisGraphNode) => void;
    height?: string;
    showSettings?: boolean;
}

export const LocalSubgraph: React.FC<LocalSubgraphProps> = ({ 
    nodeId, 
    depth = 1,
    onNodeClick,
    height = '400px',
    showSettings = true
}) => {
    const [nodes, setNodes] = useState<VisGraphNode[]>([]);
    const [edges, setEdges] = useState<VisGraphEdge[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [physics, setPhysics] = useState(false);
    const [showDimensions, setShowDimensions] = useState(false);
    const [labelMode, setLabelMode] = useState<'hover' | 'always' | 'never'>('hover');
    const [nodeSize, setNodeSize] = useState<'small' | 'medium' | 'large'>('medium');

    useEffect(() => {
        if (!nodeId) {
            setLoading(false);
            return;
        }

        const abortController = new AbortController();
        setLoading(true);
        setError(null);

        const fetchGraph = async () => {
            try {
                // First try local subgraph
                const localRes = await api.get(`/api/graph/local?node=${encodeURIComponent(nodeId)}&depth=${depth}`, {
                    signal: abortController.signal
                });

                if (abortController.signal.aborted) return;
                let localNodes = Array.isArray(localRes.data.nodes) ? localRes.data.nodes : [];
                let localEdges = Array.isArray(localRes.data.edges) ? localRes.data.edges : [];

                // If only center node returned, fallback to filtered graph with depth 2
                if (localNodes.length <= 1) {
                    const filteredRes = await api.get(`/api/graph/filtered?root=${encodeURIComponent(nodeId)}&depth=${Math.max(depth, 2)}`, {
                        signal: abortController.signal
                    });
                    if (abortController.signal.aborted) return;
                    localNodes = Array.isArray(filteredRes.data.nodes) ? filteredRes.data.nodes : localNodes;
                    localEdges = Array.isArray(filteredRes.data.edges) ? filteredRes.data.edges : localEdges;
                }

                // Convert to VisGraph format
                const visNodes: VisGraphNode[] = localNodes
                    .filter((n: any) => n && (n.id || n.name))
                    .map((n: any) => {
                        const nodeKey = (n.id || n.name || '').toString();
                        const label = (n.label || n.name || nodeKey).toString();
                        const nodeType = n.type || 'model';
                        const isCenter = nodeKey === nodeId;
                        
                        const tooltipParts = [label, `Type: ${nodeType}`];
                        if (n.entity_type) tooltipParts.push(`Entity: ${n.entity_type}`);
                        if (n.physical_location) tooltipParts.push(`Physical: ${n.physical_location}`);
                        
                        return {
                            id: nodeKey,
                            label: label.length > 30 ? label.substring(0, 27) + '...' : label,
                            type: nodeType as 'entity' | 'metric' | 'dimension' | 'model',
                            title: tooltipParts.join('\n'),
                            ...(isCenter && { color: { background: '#00e5ff', border: '#00e5ff', font: { color: '#000' } } })
                        };
                    });

                const visEdges: VisGraphEdge[] = localEdges
                    .filter((e: any) => {
                        if (!e || !e.from || !e.to) return false;
                        return visNodes.some(n => n.id === e.from) && visNodes.some(n => n.id === e.to);
                    })
                    .map((e: any) => ({
                        from: e.from?.toString(),
                        to: e.to?.toString(),
                        label: e.fk && e.pk ? `${e.fk} → ${e.pk}` : '',
                        type: e.type || 'relationship'
                    }));

                setNodes(visNodes);
                setEdges(visEdges);
                setLoading(false);
            } catch (error: any) {
                if (error.name === 'AbortError' || error.name === 'CanceledError' || error.code === 'ERR_CANCELED') {
                    return;
                }
                console.error('Failed to load local subgraph:', error);
                setError(`Failed to load graph: ${error.message || 'Unknown error'}`);
                setLoading(false);
            }
        };

        fetchGraph();

        return () => {
            abortController.abort();
        };
    }, [nodeId, depth]);

    if (loading) {
        return (
            <div className="flex items-center justify-center" style={{ height }}>
                <Loader2 className="animate-spin text-cyan-500 w-6 h-6" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center text-red-400 text-sm" style={{ height }}>
                <AlertCircle className="w-4 h-4 mr-2" />
                {error}
            </div>
        );
    }

    const displayedNodes = showDimensions ? nodes : nodes.filter(n => n.type !== 'dimension');
    const displayedEdges = edges.filter(e => showDimensions || (!e.from?.toString().startsWith('dimension') && !e.to?.toString().startsWith('dimension')));

    return (
        <div className="rounded-xl border border-white/10 bg-[#0f172a] overflow-hidden" style={{ minHeight: height }}>
            {showSettings && (
                <div className="flex flex-wrap gap-3 p-3 border-b border-white/5 text-xs text-slate-300">
                    <label className="flex items-center gap-1">
                        <input type="checkbox" checked={physics} onChange={(e) => setPhysics(e.target.checked)} /> Physics
                    </label>
                    <label className="flex items-center gap-1">
                        <input type="checkbox" checked={showDimensions} onChange={(e) => setShowDimensions(e.target.checked)} /> Dimensions
                    </label>
                    <label className="flex items-center gap-1">
                        Labels:
                        <select value={labelMode} onChange={(e) => setLabelMode(e.target.value as any)} className="bg-[#0f172a] border border-white/10 rounded px-2 py-1">
                            <option value="hover">Hover</option>
                            <option value="always">Always</option>
                            <option value="never">Never</option>
                        </select>
                    </label>
                    <label className="flex items-center gap-1">
                        Size:
                        <select value={nodeSize} onChange={(e) => setNodeSize(e.target.value as any)} className="bg-[#0f172a] border border-white/10 rounded px-2 py-1">
                            <option value="small">Small</option>
                            <option value="medium">Medium</option>
                            <option value="large">Large</option>
                        </select>
                    </label>
                </div>
            )}
            <div style={{ height }}>
                <SemanticGraph
                    nodes={displayedNodes}
                    edges={displayedEdges}
                    onNodeClick={onNodeClick}
                    height={height}
                    focusNodeId={nodeId}
                    physics={physics}
                    labelMode={labelMode}
                    nodeSize={nodeSize}
                />
            </div>
        </div>
    );
};
