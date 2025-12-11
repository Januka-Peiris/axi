import { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { VisGraph } from './graph/VisGraph';
import type { VisGraphNode, VisGraphEdge } from './graph/types';

export const GraphView = () => {
    const [nodes, setNodes] = useState<VisGraphNode[]>([]);
    const [edges, setEdges] = useState<VisGraphEdge[]>([]);

    useEffect(() => {
        const abortController = new AbortController();

        api.get(endpoints.graph, { signal: abortController.signal })
            .then(res => {
                if (abortController.signal.aborted) return;

                const raw = res.data;
                const visNodes: VisGraphNode[] = [];
                const visEdges: VisGraphEdge[] = [];

                // Convert nodes
                if (Array.isArray(raw.nodes)) {
                    raw.nodes.forEach((n: string | { name?: string; type?: string }) => {
                        const nodeName = typeof n === 'string' ? n : (n.name || 'unknown');
                        const nodeType = typeof n === 'object' ? (n.type || 'model') : 'model';
                        visNodes.push({
                            id: nodeName,
                            label: nodeName,
                            type: nodeType as 'entity' | 'metric' | 'dimension' | 'model',
                            title: nodeName
                        });
                    });
                }

                // Convert edges
                if (Array.isArray(raw.edges)) {
                    raw.edges.forEach((e: { from?: string; to?: string; fk?: string; pk?: string; type?: string }, i: number) => {
                        if (!e.from || !e.to) return;
                        visEdges.push({
                            id: `e${i}`,
                            from: e.from,
                            to: e.to,
                            label: e.fk && e.pk ? `${e.fk} -> ${e.pk}` : '',
                            type: e.type || 'relationship'
                        });
                    });
                }

                setNodes(visNodes);
                setEdges(visEdges);
            })
            .catch(error => {
                if (error.name !== 'AbortError') {
                    console.error('Failed to load graph data:', error);
                }
            });

        return () => {
            abortController.abort();
        };
    }, []);

    return (
        <div style={{ height: '70vh', border: '1px solid var(--border-color)', borderRadius: '0.5rem', background: '#0f172a' }}>
            <VisGraph
                nodes={nodes}
                edges={edges}
                height="100%"
                enablePhysics={true}
            />
        </div>
    );
};
