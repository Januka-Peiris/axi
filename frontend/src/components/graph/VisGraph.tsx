import React, { useEffect, useRef, useState } from 'react';
import type { Network, NodeOptions, Options } from 'vis-network';
import type { DataSet as VisDataSet } from 'vis-data';
import type { VisGraphNode, VisGraphEdge, VisGraphProps } from './types';

// Re-export types
export type { VisGraphNode, VisGraphEdge, VisGraphProps } from './types';

// Node color mapping
const getNodeColor = (type: string): { background: string; border: string; font: { color: string } } => {
    switch (type) {
        case 'entity':
            return { background: '#3b82f6', border: '#2563eb', font: { color: '#fff' } };
        case 'metric':
            return { background: '#a855f7', border: '#9333ea', font: { color: '#fff' } };
        case 'dimension':
            return { background: '#14b8a6', border: '#0d9488', font: { color: '#fff' } };
        case 'model':
            return { background: '#64748b', border: '#475569', font: { color: '#fff' } };
        case 'category':
            return { background: '#1e293b', border: '#334155', font: { color: '#fff' } };
        default:
            return { background: '#64748b', border: '#475569', font: { color: '#fff' } };
    }
};

export const VisGraph: React.FC<VisGraphProps> = ({
    nodes,
    edges,
    onNodeClick,
    onNodeHover,
    height = '600px',
    focusNodeId,
    enableClustering = false,
    enablePhysics = true,
    onStabilizationEnd
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const networkRef = useRef<Network | null>(null);
    const [isStabilizing, setIsStabilizing] = useState(true);

    useEffect(() => {
        let cancelled = false;
        if (!containerRef.current) return;
        setIsStabilizing(true);

        const init = async () => {
            try {
                const [{ Network }, { DataSet }] = await Promise.all([import('vis-network'), import('vis-data')]);
                if (cancelled || !containerRef.current) return;

                // Convert nodes to vis-network format
                const visNodes = nodes.map(node => {
                    const colors = getNodeColor(node.type || 'model');
                    return {
                        ...node,
                        id: node.id,
                        label: node.label || node.id,
                        title: node.title || `${node.label || node.id}\nType: ${node.type || 'model'}`,
                        color: colors,
                        shape: 'dot',
                        size: node.type === 'category' ? 25 : 20,
                        font: {
                            size: nodes.length > 150 ? 10 : 12,
                            color: colors.font.color,
                            face: 'Inter, system-ui, sans-serif'
                        },
                        borderWidth: 2
                    };
                });

                // Convert edges to vis-network format
                const visEdges = edges.map(edge => ({
                    ...edge,
                    from: edge.from,
                    to: edge.to,
                    label: edge.label || '',
                    arrows: { to: { enabled: true, scaleFactor: 0.8 } },
                    smooth: {
                        type: 'curved',
                        roundness: 0.5
                    },
                    color: { color: '#00e5ff', highlight: '#00e5ff', opacity: 0.7 },
                    width: 2
                }));

                const nodesDataSet: VisDataSet<VisGraphNode> = new DataSet<VisGraphNode>(visNodes);
                const edgesDataSet: VisDataSet<VisGraphEdge> = new DataSet<VisGraphEdge>(visEdges);

                const data = {
                    nodes: nodesDataSet,
                    edges: edgesDataSet
                };

                const options: Options = {
                    physics: {
                        enabled: enablePhysics,
                        barnesHut: {
                            gravitationalConstant: -30000,
                            centralGravity: 0.3,
                            springLength: 120,
                            springConstant: 0.04,
                            avoidOverlap: 1,
                            damping: 0.09
                        },
                        stabilization: {
                            enabled: true,
                            iterations: 200,
                            fit: true
                        }
                    },
                    nodes: {
                        shape: 'dot',
                        font: {
                            size: nodes.length > 150 ? 10 : 12
                        },
                        borderWidth: 2,
                        shadow: false
                    },
                    edges: {
                        smooth: {
                            enabled: true,
                            type: 'curved',
                            roundness: 0.5
                        },
                        arrows: {
                            to: {
                                enabled: true,
                                scaleFactor: 0.8
                            }
                        },
                        color: {
                            color: '#00e5ff',
                            highlight: '#00e5ff',
                            opacity: 0.7
                        },
                        width: 2
                    },
                    interaction: {
                        hover: true,
                        tooltipDelay: 200,
                        zoomView: true,
                        dragView: true
                    },
                    layout: {
                        improvedLayout: true
                    }
                };

                // Create network
                const network = new Network(containerRef.current, data, options);
                networkRef.current = network;

                network.on('stabilized', () => {
                    setIsStabilizing(false);
                    if (onStabilizationEnd) {
                        onStabilizationEnd();
                    }
                });

                // Handle node click
                if (onNodeClick) {
                    network.on('click', (params) => {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0] as string;
                            const node = nodes.find(n => n.id === nodeId);
                            if (node) {
                                onNodeClick(nodeId, node);
                            }
                        }
                    });
                }

                // Handle node hover
                if (onNodeHover) {
                    network.on('hoverNode', (params) => {
                        onNodeHover(params.node as string);
                    });
                    network.on('blurNode', () => {
                        onNodeHover(null);
                    });
                }

                // Focus on node if specified
                if (focusNodeId) {
                    setTimeout(() => {
                        if (!networkRef.current) return;
                        networkRef.current.focus(focusNodeId, {
                            scale: 1.5,
                            animation: {
                                duration: 400,
                                easingFunction: 'easeInOutQuad'
                            }
                        });
                        
                        const connectedNodes = networkRef.current.getConnectedNodes(focusNodeId) as string[];

                        const updateNodes = visNodes.map(node => {
                            if (node.id === focusNodeId) {
                                return { ...node, color: { ...node.color, border: '#00e5ff', background: '#00e5ff' } };
                            } else if (connectedNodes.includes(node.id)) {
                                return node;
                            } else {
                                return { ...node, opacity: 0.1 };
                            }
                        });
                        
                        data.nodes.update(updateNodes);
                    }, 100);
                }
            } catch (err) {
                console.error('Failed to load graph dependencies', err);
                setIsStabilizing(false);
            }
        };

        void init();

        // Cleanup
        return () => {
            cancelled = true;
            if (networkRef.current) {
                networkRef.current.destroy();
                networkRef.current = null;
            }
        };
    }, [nodes, edges, focusNodeId, enablePhysics, onNodeClick, onNodeHover, onStabilizationEnd]);

    // Clustering support
    useEffect(() => {
        if (!networkRef.current || !enableClustering) return;

        const network = networkRef.current;
        
        // Cluster by type
        const clusters: Record<string, string[]> = {};
        nodes.forEach(node => {
            const type = node.type || 'model';
            if (!clusters[type]) {
                clusters[type] = [];
            }
            clusters[type].push(node.id);
        });

        // Apply clustering
        Object.entries(clusters).forEach(([type, nodeIds]) => {
            if (nodeIds.length > 1) {
                network.cluster({
                    joinCondition: (nodeOptions: any) => {
                        return nodeIds.includes(nodeOptions.id);
                    },
                    clusterNodeProperties: {
                        id: `${type}_cluster`,
                        label: `${type} (${nodeIds.length})`,
                        color: getNodeColor(type),
                        shape: 'box',
                        size: 30
                    } as Partial<NodeOptions>
                });
            }
        });
    }, [nodes, enableClustering]);

    return (
        <div className="relative w-full" style={{ height }}>
            {isStabilizing && (
                <div className="absolute top-4 right-4 z-10 bg-[#151821] border border-white/10 rounded-lg px-3 py-2 text-xs text-slate-400">
                    Stabilizing layout...
                </div>
            )}
            <div ref={containerRef} className="w-full h-full" style={{ background: '#0f172a' }} />
        </div>
    );
};
