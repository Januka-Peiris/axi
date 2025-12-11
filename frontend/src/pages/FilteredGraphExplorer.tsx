import { useRef, useState } from 'react';
import { api } from '../api/client';
import { Loader2, AlertCircle, Search } from 'lucide-react';
import { VisGraph } from '../components/graph/VisGraph';
import type { VisGraphNode, VisGraphEdge } from '../components/graph/types';

export const FilteredGraphExplorer = () => {
    const [nodes, setNodes] = useState<VisGraphNode[]>([]);
    const [edges, setEdges] = useState<VisGraphEdge[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    // Filter state
    const [rootNode, setRootNode] = useState('');
    const [depth, setDepth] = useState(2);
    const [searchQuery, setSearchQuery] = useState('');
    const [showEntities, setShowEntities] = useState(true);
    const [showMetrics, setShowMetrics] = useState(true);
    const [showDimensions, setShowDimensions] = useState(true);
    const [enableClustering, setEnableClustering] = useState(false);
    const [enablePhysics, setEnablePhysics] = useState(true);
    const [focusNodeId, setFocusNodeId] = useState<string | undefined>(undefined);

    const containerRef = useRef<HTMLDivElement>(null);

    const loadGraph = () => {
        if (!rootNode.trim()) {
            setError('Please enter a root node name');
            return;
        }

        setLoading(true);
        setError(null);
        setFocusNodeId(undefined);

        const params = new URLSearchParams({
            root: rootNode.trim(),
            depth: depth.toString()
        });

        api.get(`/api/graph/filtered?${params.toString()}`)
            .then(res => {
                if (res.data.error) {
                    setError(res.data.error);
                    setNodes([]);
                    setEdges([]);
                    setLoading(false);
                    return;
                }

                const rawNodes = Array.isArray(res.data.nodes) ? res.data.nodes : [];
                const rawEdges = Array.isArray(res.data.edges) ? res.data.edges : [];

                // Filter by search query and type
                let filteredNodes = rawNodes;
                if (searchQuery.trim()) {
                    const query = searchQuery.toLowerCase();
                    filteredNodes = filteredNodes.filter((n: any) => 
                        n.name && n.name.toLowerCase().includes(query)
                    );
                }

                // Filter by type
                filteredNodes = filteredNodes.filter((n: any) => {
                    const nodeType = n.type || 'model';
                    if (nodeType === 'entity' || nodeType === 'model') return showEntities;
                    if (nodeType === 'metric') return showMetrics;
                    if (nodeType === 'dimension') return showDimensions;
                    return true;
                });

                // Convert to VisGraph format
                const visNodes: VisGraphNode[] = filteredNodes
                    .filter((n: any) => n && n.name && typeof n.name === 'string')
                    .map((n: any) => {
                        const nodeName = n.name.trim();
                        const nodeType = n.type || 'model';
                        const isRoot = nodeName === rootNode.trim();
                        
                        const tooltipParts = [nodeName, `Type: ${nodeType}`];
                        if (n.path) tooltipParts.push(`Path: ${n.path}`);
                        if (n.source_tables) tooltipParts.push(`Source: ${Array.isArray(n.source_tables) ? n.source_tables.join(', ') : n.source_tables}`);
                        
                        return {
                            id: nodeName,
                            label: nodeName.length > 30 ? nodeName.substring(0, 27) + '...' : nodeName,
                            type: nodeType as 'entity' | 'metric' | 'dimension' | 'model',
                            title: tooltipParts.join('\n'),
                            ...(isRoot && { color: { background: '#00e5ff', border: '#00e5ff', font: { color: '#000' } } })
                        };
                    });

                // Warn if too many nodes
                if (visNodes.length > 200) {
                    setError(`Graph too large (${visNodes.length} nodes). Please narrow your filters.`);
                    setNodes([]);
                    setEdges([]);
                    setLoading(false);
                    return;
                }

                const visEdges: VisGraphEdge[] = rawEdges
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
                setFocusNodeId(rootNode.trim());
                setLoading(false);
            })
            .catch(error => {
                console.error('Failed to load filtered graph:', error);
                setError(`Failed to load graph: ${error.message || 'Unknown error'}`);
                setLoading(false);
            });
    };

    return (
        <div className="h-full flex flex-col bg-background">
            <div className="p-4 border-b border-white/10 bg-[#151821]">
                <h2 className="text-xl font-bold text-white mb-4">Filtered Graph Explorer</h2>
                
                {/* Filter Controls */}
                <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label className="block text-sm text-slate-400 mb-1">Root Node</label>
                            <input
                                type="text"
                                value={rootNode}
                                onChange={(e) => setRootNode(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && loadGraph()}
                                placeholder="Enter node name..."
                                className="w-full bg-[#0f172a] border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-slate-400 mb-1">Depth</label>
                            <select
                                value={depth}
                                onChange={(e) => setDepth(Number(e.target.value))}
                                className="w-full bg-[#0f172a] border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
                            >
                                <option value={1}>1 hop</option>
                                <option value={2}>2 hops</option>
                                <option value={3}>3 hops</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm text-slate-400 mb-1">Search</label>
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="Filter nodes..."
                                    className="w-full bg-[#0f172a] border border-white/10 rounded-lg py-2 pl-9 pr-3 text-sm text-white focus:outline-none focus:border-cyan-500/50"
                                />
                            </div>
                        </div>
                    </div>
                    
                    <div className="flex items-center gap-4 flex-wrap">
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="show-entities"
                                checked={showEntities}
                                onChange={(e) => setShowEntities(e.target.checked)}
                                className="w-4 h-4 rounded border-white/20 bg-[#0f172a] text-cyan-500 focus:ring-cyan-500"
                            />
                            <label htmlFor="show-entities" className="text-sm text-slate-300">Entities</label>
                        </div>
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="show-metrics"
                                checked={showMetrics}
                                onChange={(e) => setShowMetrics(e.target.checked)}
                                className="w-4 h-4 rounded border-white/20 bg-[#0f172a] text-cyan-500 focus:ring-cyan-500"
                            />
                            <label htmlFor="show-metrics" className="text-sm text-slate-300">Metrics</label>
                        </div>
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="show-dimensions"
                                checked={showDimensions}
                                onChange={(e) => setShowDimensions(e.target.checked)}
                                className="w-4 h-4 rounded border-white/20 bg-[#0f172a] text-cyan-500 focus:ring-cyan-500"
                            />
                            <label htmlFor="show-dimensions" className="text-sm text-slate-300">Dimensions</label>
                        </div>
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="enable-clustering"
                                checked={enableClustering}
                                onChange={(e) => setEnableClustering(e.target.checked)}
                                className="w-4 h-4 rounded border-white/20 bg-[#0f172a] text-cyan-500 focus:ring-cyan-500"
                            />
                            <label htmlFor="enable-clustering" className="text-sm text-slate-300">Cluster</label>
                        </div>
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="enable-physics"
                                checked={enablePhysics}
                                onChange={(e) => setEnablePhysics(e.target.checked)}
                                className="w-4 h-4 rounded border-white/20 bg-[#0f172a] text-cyan-500 focus:ring-cyan-500"
                            />
                            <label htmlFor="enable-physics" className="text-sm text-slate-300">Physics</label>
                        </div>
                    </div>
                    
                    <button
                        onClick={loadGraph}
                        disabled={loading || !rootNode.trim()}
                        className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
                    >
                        {loading ? 'Loading...' : 'Load Graph'}
                    </button>
                </div>
            </div>

            <div 
                ref={containerRef}
                className="flex-1 relative min-h-[640px] bg-[#0f172a]" 
                style={{ width: '100%', height: 'calc(100vh - 250px)' }}
            >
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
                        <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
                    </div>
                )}
                {error && (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
                        <div className="text-center max-w-md p-6">
                            <AlertCircle className="text-red-400 w-12 h-12 mx-auto mb-4" />
                            <p className="text-red-400 font-semibold mb-2">Error</p>
                            <p className="text-slate-400 text-sm">{error}</p>
                        </div>
                    </div>
                )}
                {nodes.length > 0 && (
                    <VisGraph
                        nodes={nodes}
                        edges={edges}
                        onNodeClick={(nodeId, node) => {
                            setFocusNodeId(nodeId);
                            console.log('Node clicked:', node);
                        }}
                        height="100%"
                        focusNodeId={focusNodeId}
                        enableClustering={enableClustering}
                        enablePhysics={enablePhysics}
                    />
                )}
                {!loading && !error && nodes.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <p className="text-slate-400 text-sm">Enter a root node and click "Load Graph" to begin</p>
                    </div>
                )}
            </div>
        </div>
    );
};
