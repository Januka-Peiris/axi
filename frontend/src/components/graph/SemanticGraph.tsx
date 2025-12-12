import React from 'react';
import { VisGraph } from './VisGraph';
import type { VisGraphNode, VisGraphEdge } from './types';

interface Props {
  nodes: VisGraphNode[];
  edges: VisGraphEdge[];
  onNodeClick?: (nodeId: string, node: VisGraphNode) => void;
  onNodeDoubleClick?: (nodeId: string, node: VisGraphNode) => void;
  height?: string;
  physics?: boolean;
  clustering?: boolean;
  focusNodeId?: string;
  labelMode?: 'hover' | 'always' | 'never';
  nodeSize?: 'small' | 'medium' | 'large';
  highlightNodeIds?: string[];
  highlightEdgeIds?: string[];
  onNodeHover?: (nodeId: string | null) => void;
}

export const SemanticGraph: React.FC<Props> = ({
  nodes,
  edges,
  onNodeClick,
  height = '600px',
  physics = false,
  clustering = false,
  focusNodeId,
  labelMode = 'hover',
  nodeSize = 'medium',
  highlightNodeIds,
  highlightEdgeIds,
  onNodeHover
}) => {
  return (
    <VisGraph
      nodes={nodes}
      edges={edges}
      onNodeClick={onNodeClick}
      onNodeHover={onNodeHover}
      height={height}
      focusNodeId={focusNodeId}
      enablePhysics={physics}
      enableClustering={clustering}
      onStabilizationEnd={() => {}}
      labelMode={labelMode}
      nodeSize={nodeSize}
      highlightNodeIds={highlightNodeIds}
      highlightEdgeIds={highlightEdgeIds}
    />
  );
};
