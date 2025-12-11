import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Loader2, AlertCircle } from 'lucide-react';
import { VisGraph } from './VisGraph';
import type { VisGraphNode, VisGraphEdge } from './types';

interface LocalSubgraphProps {
    nodeId: string;
    depth?: number;
    onNodeClick?: (nodeId: string, node: VisGraphNode) => void;
    height?: string;
}

export const LocalSubgraph: React.FC<LocalSubgraphProps> = ({ 
    nodeId, 
    depth = 1,
    onNodeClick,
    height = '400px'
}) => {
    const [nodes, setNodes] = useState<VisGraphNode[]>([]);
    const [edges, setEdges] = useState<VisGraphEdge[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

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
                    .filter((n: any) => n && n.name && typeof n.name === 'string')
                    .map((n: any) => {
                        const nodeName = n.name.trim();
                        const nodeType = n.type || 'model';
                        const isCenter = nodeName === nodeId;
                        
                        // Build tooltip
                        const tooltipParts = [nodeName, `Type: ${nodeType}`];
                        if (n.path) tooltipParts.push(`Path: ${n.path}`);
                        if (n.source_tables) tooltipParts.push(`Source: ${Array.isArray(n.source_tables) ? n.source_tables.join(', ') : n.source_tables}`);
                        
                        return {
                            id: nodeName,
                            label: nodeName.length > 30 ? nodeName.substring(0, 27) + '...' : nodeName,
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
                        from: e.from,
                        to: e.to,
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

    return (
        <div className="rounded-xl border border-white/10 bg-[#0f172a] overflow-hidden" style={{ height }}>
            <VisGraph
                nodes={nodes}
                edges={edges}
                onNodeClick={onNodeClick}
                height={height}
                focusNodeId={nodeId}
                enablePhysics={true}
            />
        </div>
    );
};
