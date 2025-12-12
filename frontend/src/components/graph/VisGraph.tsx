import React, { useEffect, useRef, useState } from 'react';
import type { Network, NodeOptions, Options } from 'vis-network';
import type { DataSet as VisDataSet } from 'vis-data';
import type { VisGraphNode, VisGraphEdge, VisGraphProps } from './types';

// Re-export types
export type { VisGraphNode, VisGraphEdge, VisGraphProps } from './types';

// Node color mapping
const getNodeColor = (type: string, promotion?: string): { background: string; border: string; font: { color: string } } => {
    const base = (() => {
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
    })();
    if (promotion === 'promoted') {
        return { ...base, border: '#22c55e' };
    }
    if (promotion === 'error') {
        return { ...base, border: '#ef4444' };
    }
    if (promotion === 'ignored') {
        return { ...base, border: '#94a3b8' };
    }
    return base;
};

export const VisGraph: React.FC<VisGraphProps> = ({
    nodes,
    edges,
    onNodeClick,
    onNodeHover,
    height = '600px',
    focusNodeId,
    enableClustering = false,
    enablePhysics = false,
    onStabilizationEnd,
    labelMode = 'hover',
    nodeSize = 'medium',
    highlightNodeIds = [],
    highlightEdgeIds = []
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const networkRef = useRef<Network | null>(null);
    const [isStabilizing, setIsStabilizing] = useState(enablePhysics);

    useEffect(() => {
        let cancelled = false;
        if (!containerRef.current) return;
        setIsStabilizing(enablePhysics);

        const init = async () => {
            try {
                const [{ Network }, { DataSet }] = await Promise.all([import('vis-network'), import('vis-data')]);
                if (cancelled || !containerRef.current) return;

                const sizeMap = { small: 14, medium: 20, large: 28 };
                const baseLabelSize = nodes.length > 150 ? 10 : 12;
                const defaultLabelSize = labelMode === 'always' ? baseLabelSize : 0;

                // Convert nodes to vis-network format
                const visNodes = nodes.map(node => {
                    const colors = getNodeColor(node.type || 'model', (node as any).promotion_status || (node as any).promotion);
                    return {
                        ...node,
                        id: node.id,
                        label: node.label || node.id,
                        title: node.title || `${node.label || node.id}\nType: ${node.type || 'model'}`,
                        color: colors,
                        shape: 'dot',
                        size: node.type === 'category' ? sizeMap[nodeSize] + 6 : sizeMap[nodeSize],
                        font: {
                            size: defaultLabelSize,
                            color: colors.font.color,
                            face: 'Inter, system-ui, sans-serif'
                        },
                        borderWidth: 2
                    };
                });

                // Convert edges to vis-network format
                const visEdges = edges.map(edge => {
                    const edgeId = edge.id || `${edge.from}->${edge.to}`;
                    return {
                        ...edge,
                        id: edgeId,
                        from: edge.from,
                        to: edge.to,
                        label: edge.label || '',
                        arrows: { to: { enabled: true, scaleFactor: 0.8 } },
                        color: { color: '#00e5ff', highlight: '#00e5ff', opacity: 0.7 },
                        width: 2
                    };
                });

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
                        stabilization: enablePhysics
                            ? {
                                enabled: true,
                                iterations: 200,
                                fit: true
                              }
                            : false
                    },
                    nodes: {
                        shape: 'dot',
                        font: {
                            size: defaultLabelSize
                        },
                        borderWidth: 2,
                        shadow: false
                    },
                    edges: {
                        smooth: false as any,
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

                const applyHighlighting = () => {
                    if (!networkRef.current) return;
                    const nodeSet = new Set(highlightNodeIds);
                    const edgeSet = new Set(highlightEdgeIds);
                    const shouldDim = nodeSet.size > 0 || edgeSet.size > 0;

                    const updatedNodes = visNodes.map(node => {
                        const isHighlighted = nodeSet.has(node.id);
                        if (!shouldDim) return node;
                        return {
                            ...node,
                            color: isHighlighted ? { ...(node as any).color, border: '#eab308' } : (node as any).color,
                            opacity: isHighlighted ? 1 : 0.15,
                            font: {
                                ...(node.font || {}),
                                size: labelMode === 'always' ? baseLabelSize : node.font?.size || defaultLabelSize
                            }
                        };
                    });

                    const updatedEdges = visEdges.map(edge => {
                        const id = edge.id || `${edge.from}->${edge.to}`;
                        const isHighlighted = edgeSet.has(id);
                        if (!shouldDim) return edge;
                        return {
                            ...edge,
                            color: isHighlighted ? { color: '#eab308', highlight: '#eab308', opacity: 0.9 } : edge.color,
                            width: isHighlighted ? 3 : 1
                        };
                    });

                    data.nodes.update(updatedNodes);
                    data.edges.update(updatedEdges);
                };

                applyHighlighting();

                if (enablePhysics) {
                    network.on('stabilized', () => {
                        setIsStabilizing(false);
                        if (onStabilizationEnd) {
                            onStabilizationEnd();
                        }
                    });
                } else {
                    setIsStabilizing(false);
                }

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
                if (onNodeHover || labelMode === 'hover') {
                    const resetLabels = () => {
                        data.nodes.update(visNodes.map(n => ({
                            id: n.id,
                            font: { ...(n.font || {}), size: labelMode === 'always' ? baseLabelSize : 0 }
                        })));
                    };

                    network.on('hoverNode', (params) => {
                        if (onNodeHover) onNodeHover(params.node as string);
                        if (labelMode === 'hover') {
                            const hoveredId = params.node as string;
                            const neighborIds = network.getConnectedNodes(hoveredId) as string[];
                            const idsToShow = new Set([hoveredId, ...neighborIds]);
                            data.nodes.update(
                                visNodes.map(n => ({
                                    id: n.id,
                                    font: { ...(n.font || {}), size: idsToShow.has(n.id) ? baseLabelSize : 0 }
                                }))
                            );
                        }
                    });
                    network.on('blurNode', () => {
                        if (onNodeHover) onNodeHover(null);
                        if (labelMode === 'hover') {
                            resetLabels();
                        }
                    });

                    if (labelMode === 'hover') {
                        resetLabels();
                    }
                }

                // Focus on node if specified
                if (focusNodeId) {
                    setTimeout(() => {
                        if (!networkRef.current) return;
                        networkRef.current.focus(focusNodeId, {
                            scale: 1.3,
                            animation: {
                                duration: 400,
                                easingFunction: 'easeInOutQuad'
                            }
                        });
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
    }, [nodes, edges, focusNodeId, enablePhysics, onNodeClick, onNodeHover, onStabilizationEnd, labelMode, nodeSize, highlightNodeIds, highlightEdgeIds]);

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
