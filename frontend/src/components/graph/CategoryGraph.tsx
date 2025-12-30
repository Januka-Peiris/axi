import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Loader2, AlertCircle } from 'lucide-react';
import { VisGraph } from './VisGraph';
import type { VisGraphNode, VisGraphEdge } from './types';

export const CategoryGraph = () => {
    const [nodes, setNodes] = useState<VisGraphNode[]>([]);
    const [edges, setEdges] = useState<VisGraphEdge[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

    const loadCategories = () => {
        setLoading(true);
        setError(null);

        api.get('/api/graph/category')
            .then(res => {
                const rawNodes = Array.isArray(res.data.nodes) ? res.data.nodes : [];
                
                const categoryNodes: VisGraphNode[] = rawNodes.map((cat: any, idx: number) => ({
                    id: cat.name || `category_${idx}`,
                    label: `${cat.category_type || 'unknown'} (${cat.count || 0})`,
                    type: 'category',
                    title: `${cat.category_type || 'unknown'}\nCount: ${cat.count || 0}\nClick to expand`,
                    count: cat.count || 0,
                    categoryType: cat.category_type || 'unknown'
                }));

                setNodes(categoryNodes);
                setEdges([]);
                setLoading(false);
            })
            .catch(error => {
                console.error('Failed to load category graph:', error);
                setError(`Failed to load categories: ${error.message || 'Unknown error'}`);
                setLoading(false);
            });
    };

    useEffect(() => {
        loadCategories();
    }, []);

    const handleCategoryClick = async (nodeId: string, node: VisGraphNode) => {
        const categoryType = node.categoryType || '';
        const isExpanded = expandedCategories.has(categoryType);

        if (isExpanded) {
            // Collapse: remove expanded nodes
            setExpandedCategories(prev => {
                const next = new Set(prev);
                next.delete(categoryType);
                return next;
            });
            // Reload categories to reset view
            loadCategories();
        } else {
            // Expand: fetch category items
            setExpandedCategories(prev => new Set(prev).add(categoryType));
            
            try {
                const res = await api.get(`/api/graph/category?type=${categoryType}`);
                const categoryData = res.data.nodes.find((n: any) => n.category_type === categoryType);
                
                if (categoryData && categoryData.items) {
                    // Add individual nodes for this category
                    const newNodes: VisGraphNode[] = categoryData.items.slice(0, 50).map((item: string) => ({
                        id: item,
                        label: item.length > 25 ? item.substring(0, 22) + '...' : item,
                        type: 'model', // Default type for category items
                        title: item
                    }));

                    // Update the category node to show it's expanded
                    const updatedNodes = nodes.map(n => 
                        n.id === nodeId 
                            ? { ...n, label: `${n.categoryType} (${n.count}) [expanded]` }
                            : n
                    );

                    // Add edges from category to items
                    const newEdges: VisGraphEdge[] = newNodes.map(item => ({
                        from: nodeId,
                        to: item.id,
                        type: 'contains'
                    }));

                    setNodes([...updatedNodes, ...newNodes]);
                    setEdges([...edges, ...newEdges]);
                }
            } catch (error) {
                console.error('Failed to expand category:', error);
            }
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-96 text-red-400 text-sm">
                <AlertCircle className="w-4 h-4 mr-2" />
                {error}
            </div>
        );
    }

    return (
        <div className="rounded-xl border border-white/10 bg-[#0f172a] overflow-hidden" style={{ height: '600px' }}>
            <VisGraph
                nodes={nodes}
                edges={edges}
                onNodeClick={handleCategoryClick}
                height="600px"
                enableClustering={false}
                enablePhysics={true}
            />
        </div>
    );
};
