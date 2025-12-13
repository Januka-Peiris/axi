// Graph type definitions
export interface VisGraphNode {
    id: string;
    label: string;
    type: 'entity' | 'metric' | 'dimension' | 'model' | 'category';
    title?: string;
    group?: string;
    promotion_status?: string;
    [key: string]: any;
}

export interface VisGraphEdge {
    id?: string;
    from: string;
    to: string;
    label?: string;
    type?: string;
    [key: string]: any;
}

export interface VisGraphProps {
    nodes: VisGraphNode[];
    edges: VisGraphEdge[];
    onNodeClick?: (nodeId: string, node: VisGraphNode) => void;
    onNodeHover?: (nodeId: string | null) => void;
    height?: string;
    focusNodeId?: string;
    enableClustering?: boolean;
    enablePhysics?: boolean;
    onStabilizationEnd?: () => void;
    labelMode?: 'hover' | 'always' | 'never';
    nodeSize?: 'small' | 'medium' | 'large';
    highlightNodeIds?: string[];
    highlightEdgeIds?: string[];
}







