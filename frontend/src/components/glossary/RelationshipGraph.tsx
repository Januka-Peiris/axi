import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import type { GlossaryEntity } from '../../api/glossary';

interface Props {
    entity: GlossaryEntity;
}

export const RelationshipGraph: React.FC<Props> = ({ entity }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const cyRef = useRef<cytoscape.Core | null>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        // Build Elements
        // Center Node
        const elements: any[] = [
            { data: { id: entity.name, label: entity.name, type: 'current' } }
        ];

        entity.relationships.forEach((rel, i) => {
            // Target Node
            const target = rel.target_entity === entity.name ? rel.source_entity : rel.target_entity;
            elements.push({ data: { id: target, label: target, type: 'neighbor' } });

            // Edge
            elements.push({
                data: {
                    id: `e${i}`,
                    source: entity.name,
                    target: target,
                    label: rel.type
                }
            });
        });

        cyRef.current = cytoscape({
            container: containerRef.current,
            elements: elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': '#1e293b',
                        'border-width': 2,
                        'border-color': '#64748b',
                        'label': 'data(label)',
                        'color': '#cbd5e1',
                        'font-size': '12px',
                        'text-valign': 'center',
                        'width': 'label',
                        'height': '30px',
                        'padding': '10px',
                        'shape': 'round-rectangle'
                    }
                },
                {
                    selector: 'node[type="current"]',
                    style: {
                        'background-color': '#00e5ff',
                        'border-color': '#00e5ff',
                        'color': '#000',
                        'font-weight': 'bold',
                        'text-outline-color': '#00e5ff',
                        'text-outline-width': 0
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': '#475569',
                        'curve-style': 'bezier',
                        'target-arrow-shape': 'triangle',
                        'target-arrow-color': '#475569',
                        'label': 'data(label)',
                        'font-size': '10px',
                        'color': '#94a3b8',
                        'text-background-opacity': 1,
                        'text-background-color': '#0d0f15',
                        'text-background-padding': '2px'
                    }
                }
            ],
            layout: {
                name: 'concentric',
                minNodeSpacing: 50,
                padding: 20
            }
        });

        return () => {
            cyRef.current?.destroy();
        };
    }, [entity]);

    return (
        <div className="w-full h-64 bg-[#0d0f15] rounded-lg border border-white/10 overflow-hidden relative">
            <div ref={containerRef} className="w-full h-full" />
        </div>
    );
};
