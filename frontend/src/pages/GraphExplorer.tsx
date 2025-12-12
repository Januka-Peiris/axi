import { useEffect, useRef, useState } from 'react';
import { api, endpoints } from '../api/client';
import { useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';
import { VisGraph } from '../components/graph/VisGraph';
import type { VisGraphNode, VisGraphEdge } from '../components/graph/types';

export const GraphExplorer = () => {
    const [nodes, setNodes] = useState<VisGraphNode[]>([]);
    const [edges, setEdges] = useState<VisGraphEdge[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [nodeCount, setNodeCount] = useState(0);
    const [edgeCount, setEdgeCount] = useState(0);
    const [enableClustering, setEnableClustering] = useState(false);
    const [enablePhysics, setEnablePhysics] = useState(true);
    const navigate = useNavigate();
    const containerRef = useRef<HTMLDivElement>(null);
    
    // Check if debug mode is enabled
    const isDebugMode = import.meta.env.VITE_AXI_DEBUG === '1' || import.meta.env.DEV;

    useEffect(() => {
        const abortController = new AbortController();

        setLoading(true);
        setError(null);

        api.get(endpoints.graph, { signal: abortController.signal })
            .then(res => {
                if (abortController.signal.aborted) return;

                // Check for error message from backend
                if (res.data.error) {
                    setError(res.data.error);
                    setLoading(false);
                    return;
                }

                const rawNodes = Array.isArray(res.data.nodes) ? res.data.nodes : [];
                const rawEdges = Array.isArray(res.data.edges) ? res.data.edges : [];

                // Filter and process nodes
                const validNodes = rawNodes
                    .filter((n: any) => {
                        if (!n || typeof n !== 'object') return false;
                        const name = n.name || (typeof n === 'string' ? n : null);
                        return name != null && typeof name === 'string' && name.trim() !== '';
                    })
                    .map((n: any): VisGraphNode => {
                        const nodeName = (n.name || (typeof n === 'string' ? n : `node_${n}`)).trim();
                        const label = nodeName.length > 40 ? nodeName.substring(0, 37) + '...' : nodeName;
                        const nodeType = n.type || 'model';
                        
                        // Build tooltip
                        const tooltipParts = [nodeName, `Type: ${nodeType}`];
                        if (n.path) tooltipParts.push(`Path: ${n.path}`);
                        if (n.source_tables) tooltipParts.push(`Source: ${Array.isArray(n.source_tables) ? n.source_tables.join(', ') : n.source_tables}`);
                        if (n.dimensions) tooltipParts.push(`Dimensions: ${Array.isArray(n.dimensions) ? n.dimensions.join(', ') : n.dimensions}`);
                        
                        return {
                            id: nodeName,
                            label,
                            type: nodeType as 'entity' | 'metric' | 'dimension' | 'model',
                            title: tooltipParts.join('\n')
                        };
                    });

                if (validNodes.length === 0) {
                    setError('No valid nodes found in graph data. Make sure you have extracted models.');
                    setLoading(false);
                    return;
                }

                const nodeIds = new Set(validNodes.map((n: VisGraphNode) => n.id));

                // Process edges
                const visEdges: VisGraphEdge[] = rawEdges
                    .filter((e: any) => {
                        if (!e || !e.from || !e.to) return false;
                        return nodeIds.has(e.from) && nodeIds.has(e.to);
                    })
                    .map((e: any) => ({
                        from: e.from,
                        to: e.to,
                        label: e.fk && e.pk ? `${e.fk} → ${e.pk}` : '',
                        type: e.type || 'relationship'
                    }));

                // Warn if too many nodes
                if (validNodes.length > 500) {
                    setError(`Graph too large (${validNodes.length} nodes). Use filtered or local graph views instead.`);
                    setLoading(false);
                    return;
                }

                console.log(`Rendered ${validNodes.length} nodes and ${visEdges.length} edges`);

                setNodeCount(validNodes.length);
                setEdgeCount(visEdges.length);
                setNodes(validNodes);
                setEdges(visEdges);
                setLoading(false);
            })
            .catch(error => {
                if (error.name === 'AbortError' || error.name === 'CanceledError' || error.code === 'ERR_CANCELED') {
                    return;
                }
                console.error('Failed to load graph data:', error);
                setError(`Failed to load graph data: ${error.message || 'Unknown error'}`);
                setLoading(false);
            });

        return () => {
            abortController.abort();
        };
    }, [navigate]);

    const onNodeClick = (nodeId: string, node: VisGraphNode) => {
        const nodeName = node.label || nodeId;
        if (nodeName) {
            // Navigate based on node type
            if (node.type === 'metric') {
                navigate(`/metrics/${nodeName}`);
            } else if (node.type === 'dimension') {
                navigate(`/dimensions/${nodeName}`);
            } else if (node.type === 'entity') {
                navigate(`/glossary/entities/${nodeName}`);
            } else {
                navigate(`/models`);
            }
        }
    };

    // Hide legacy full graph from nav; render only for debug
    if (!isDebugMode) {
        return (
            <div className="h-full flex flex-col bg-background">
                <div className="p-4 border-b border-white/10 bg-[#151821]">
                    <h2 className="text-xl font-bold text-white">Graph Explorer</h2>
                </div>
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center max-w-md p-6">
                        <AlertCircle className="text-yellow-400 w-12 h-12 mx-auto mb-4" />
                        <p className="text-yellow-400 font-semibold mb-2">Full graph disabled.</p>
                        <p className="text-slate-400 text-sm mb-4">
                            Use the new filtered explorer.
                        </p>
                        <div className="space-y-2">
                            <button
                                onClick={() => navigate('/graph/explore')}
                                className="w-full px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white rounded-lg font-medium transition-colors"
                            >
                                Open Graph Explore
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-background">
            <div className="p-4 border-b border-white/10 flex justify-between items-center bg-[#151821]">
                <div>
                    <h2 className="text-xl font-bold text-white">Semantic Graph (Debug Mode)</h2>
                    {nodeCount > 0 && (
                        <p className="text-xs text-slate-400 mt-1">
                            {nodeCount} nodes, {edgeCount} relationships
                        </p>
                    )}
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="enable-clustering"
                            checked={enableClustering}
                            onChange={(e) => setEnableClustering(e.target.checked)}
                            className="w-4 h-4 rounded border-white/20 bg-[#0f172a] text-cyan-500 focus:ring-cyan-500"
                        />
                        <label htmlFor="enable-clustering" className="text-xs text-slate-300">Cluster</label>
                    </div>
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="enable-physics"
                            checked={enablePhysics}
                            onChange={(e) => setEnablePhysics(e.target.checked)}
                            className="w-4 h-4 rounded border-white/20 bg-[#0f172a] text-cyan-500 focus:ring-cyan-500"
                        />
                        <label htmlFor="enable-physics" className="text-xs text-slate-300">Physics</label>
                    </div>
                    <span className="text-xs text-slate-500">Powered by vis-network</span>
                </div>
            </div>
            <div 
                ref={containerRef}
                className="flex-1 relative min-h-[640px] bg-[#0f172a]" 
                style={{ width: '100%', height: 'calc(100vh - 140px)' }}
            >
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
                        <div className="text-center">
                            <Loader2 className="animate-spin text-cyan-500 w-8 h-8 mx-auto mb-2" />
                            <p className="text-slate-400 text-sm">Loading graph...</p>
                        </div>
                    </div>
                )}
                {error && (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
                        <div className="text-center max-w-md p-6">
                            <AlertCircle className="text-red-400 w-12 h-12 mx-auto mb-4" />
                            <p className="text-red-400 font-semibold mb-2">Failed to Load Graph</p>
                            <p className="text-slate-400 text-sm">{error}</p>
                        </div>
                    </div>
                )}
                {nodes.length > 0 && (
                    <VisGraph
                        nodes={nodes}
                        edges={edges}
                        onNodeClick={onNodeClick}
                        height="100%"
                        enableClustering={enableClustering}
                        enablePhysics={enablePhysics}
                    />
                )}
            </div>
        </div>
    );
};
