import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Loader2, AlertTriangle } from 'lucide-react';
import { SemanticGraph } from '../components/graph/SemanticGraph';
import type { VisGraphNode, VisGraphEdge } from '../components/graph/types';
import { useNavigate } from 'react-router-dom';

type Mode = 'local' | 'filtered' | 'categories';

export const GraphExplore = () => {
  const [mode, setMode] = useState<Mode>('local');
  const [root, setRoot] = useState('');
  const [depth, setDepth] = useState(2);
  const [types, setTypes] = useState({ entity: true, metric: true, dimension: false });
  const [promotedOnly, setPromotedOnly] = useState(false);
  const [nodes, setNodes] = useState<VisGraphNode[]>([]);
  const [edges, setEdges] = useState<VisGraphEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [physics, setPhysics] = useState(false);
    const [clustering, setClustering] = useState(false);
    const [showLabels, setShowLabels] = useState<'hover' | 'always' | 'never'>('hover');
    const [showDimensions, setShowDimensions] = useState(false);
    const [nodeSize, setNodeSize] = useState<'small' | 'medium' | 'large'>('medium');
    const [legend, setLegend] = useState(true);
    const [hoveredNode, setHoveredNode] = useState<string | null>(null);
    const [pathNodes, setPathNodes] = useState<string[]>([]);
    const [pathEdges, setPathEdges] = useState<string[]>([]);
    const [pathText, setPathText] = useState<string>('');
  const navigate = useNavigate();

  const buildParams = () => {
    const typeList = Object.entries(types)
      .filter(([, v]) => v)
      .map(([k]) => k)
      .join(',');
    return { depth, types: typeList, promoted_only: promotedOnly };
  };

  const fetchGraph = async () => {
    setLoading(true);
    setError(null);
    try {
      let res;
      if (mode === 'local') {
        if (!root) {
          setError('Select a root node');
          setLoading(false);
          return;
        }
        res = await api.get('/api/graph/local', { params: { node: root, depth } });
      } else if (mode === 'filtered') {
        if (!root) {
          setError('Select a root node');
          setLoading(false);
          return;
        }
        const params = buildParams();
        res = await api.get('/api/graph/filtered', { params: { root, ...params } });
      } else {
        res = await api.get('/api/graph/categories');
      }

      const data = res.data;
      if (data?.error) {
        setError(data.error.message || data.error.code || 'Graph error');
        setNodes([]);
        setEdges([]);
        setLoading(false);
        return;
      }

      const ns: VisGraphNode[] = (data.nodes || []).map((n: any) => ({
        id: n.id || n.name,
        label: n.label || n.name || n.id,
        type: (n.type || 'entity') as any,
        title: n.title,
        promotion_status: n.promotion_status,
      }));
      const es: VisGraphEdge[] = (data.edges || []).map((e: any) => ({
        from: e.from,
        to: e.to,
        label: e.label,
        type: e.type,
      }));

      setNodes(ns);
      setEdges(es);
    } catch (err: any) {
      setError(err?.response?.data?.error || err.message || 'Graph fetch failed');
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => {
    setPathNodes([]);
    setPathEdges([]);
    setPathText('');
    setHoveredNode(null);
  }, [root, mode]);

  const resolvePath = (targetId: string, visibleNodes: VisGraphNode[], visibleEdges: VisGraphEdge[]) => {
    if (!root) {
      setPathNodes([]);
      setPathEdges([]);
      setPathText('');
      return;
    }
    const nodeIds = new Set(visibleNodes.map(n => n.id));
    if (!nodeIds.has(root) || !nodeIds.has(targetId)) {
      setPathNodes([]);
      setPathEdges([]);
      setPathText('No join path (node missing from view)');
      return;
    }
    const adjacency = new Map<string, { neighbor: string; edgeId: string }[]>();
    visibleEdges.forEach(e => {
      const id = e.id || `${e.from}->${e.to}`;
      if (!adjacency.has(e.from)) adjacency.set(e.from, []);
      if (!adjacency.has(e.to)) adjacency.set(e.to, []);
      adjacency.get(e.from)!.push({ neighbor: e.to, edgeId: id });
      adjacency.get(e.to)!.push({ neighbor: e.from, edgeId: id });
    });

    const queue = [root];
    const visited = new Set([root]);
    const prev = new Map<string, string>();
    const prevEdge = new Map<string, string>();

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (current === targetId) break;
      const neighbors = adjacency.get(current) || [];
      neighbors.forEach(({ neighbor, edgeId }) => {
        if (visited.has(neighbor)) return;
        visited.add(neighbor);
        prev.set(neighbor, current);
        prevEdge.set(neighbor, edgeId);
        queue.push(neighbor);
      });
    }

    if (!visited.has(targetId)) {
      setPathNodes([]);
      setPathEdges([]);
      setPathText('No join path (JOIN_NOT_FOUND)');
      return;
    }

    const path: string[] = [];
    const edgePath: string[] = [];
    let cursor: string | undefined = targetId;
    while (cursor && cursor !== root) {
      path.unshift(cursor);
      const from = prev.get(cursor);
      const edge = prevEdge.get(cursor);
      if (edge) edgePath.unshift(edge);
      cursor = from;
    }
    path.unshift(root);
    setPathNodes(path);
    setPathEdges(edgePath);
    setPathText(`Path: ${path.join(' → ')}`);
  };

  const handleNodeClick = (_id: string, node: VisGraphNode) => {
    if (node.type === 'metric') navigate(`/metrics/${node.label}`);
    else if (node.type === 'dimension') navigate(`/dimensions/${node.label}`);
    else if (node.type === 'entity') navigate(`/glossary/entities/${node.label}`);
  };

  return (
    <div className="h-full flex flex-col bg-background p-4 space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => setMode('local')} className={`px-3 py-1 rounded ${mode==='local'?'bg-cyan-500 text-white':'bg-white/5 text-slate-300'}`}>Local</button>
        <button onClick={() => setMode('filtered')} className={`px-3 py-1 rounded ${mode==='filtered'?'bg-cyan-500 text-white':'bg-white/5 text-slate-300'}`}>Filtered</button>
        <button onClick={() => setMode('categories')} className={`px-3 py-1 rounded ${mode==='categories'?'bg-cyan-500 text-white':'bg-white/5 text-slate-300'}`}>Categories</button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="space-y-3 bg-[#151821] border border-white/10 rounded-lg p-4">
          <div>
            <label className="text-xs text-slate-400">Root Node</label>
            <input
              value={root}
              onChange={(e) => setRoot(e.target.value)}
              placeholder="entity.orders or metric.total_revenue"
              className="w-full bg-[#0f172a] border border-white/10 rounded px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400">Depth</label>
            <select
              value={depth}
              onChange={(e) => setDepth(parseInt(e.target.value))}
              className="w-full bg-[#0f172a] border border-white/10 rounded px-3 py-2 text-sm text-white"
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Types</label>
            {(['entity','metric','dimension'] as const).map(t => (
              <label key={t} className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={(types as any)[t]} onChange={(e) => setTypes(prev => ({...prev, [t]: e.target.checked}))} /> {t}
              </label>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={promotedOnly} onChange={(e) => setPromotedOnly(e.target.checked)} /> Promoted only
          </label>
          <button onClick={fetchGraph} className="w-full px-3 py-2 bg-cyan-500 text-white rounded">Load</button>

          <div className="border-t border-white/10 pt-3 space-y-2">
            <div className="text-xs text-slate-400">Settings</div>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={physics} onChange={(e) => setPhysics(e.target.checked)} /> Physics
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={clustering} onChange={(e) => setClustering(e.target.checked)} /> Clustering
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={showDimensions} onChange={(e) => setShowDimensions(e.target.checked)} /> Show dimensions
            </label>
            <label className="text-xs text-slate-400">Labels</label>
            <select value={showLabels} onChange={(e) => setShowLabels(e.target.value as any)} className="w-full bg-[#0f172a] border border-white/10 rounded px-3 py-2 text-sm text-white">
              <option value="hover">Hover</option>
              <option value="always">Always</option>
              <option value="never">Never</option>
            </select>
            <label className="text-xs text-slate-400">Node size</label>
            <select value={nodeSize} onChange={(e) => setNodeSize(e.target.value as any)} className="w-full bg-[#0f172a] border border-white/10 rounded px-3 py-2 text-sm text-white">
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={legend} onChange={(e) => setLegend(e.target.checked)} /> Show legend
            </label>
          </div>
        </div>

        <div className="lg:col-span-3 bg-[#0f172a] border border-white/10 rounded-lg p-2 min-h-[500px]">
          {loading ? (
            <div className="flex items-center justify-center h-full text-slate-400"><Loader2 className="animate-spin mr-2" />Loading graph...</div>
          ) : error ? (
            <div className="flex items-center justify-center h-full text-red-300 gap-2"><AlertTriangle className="w-5 h-5" />{error}</div>
          ) : (
            <div className="space-y-2">
              {(() => {
                const displayedNodes = showDimensions ? nodes : nodes.filter(n => n.type !== 'dimension');
                const displayedEdges = edges.filter(e => showDimensions || (!e.from?.toString().startsWith('dimension') && !e.to?.toString().startsWith('dimension')));
                return (
                  <SemanticGraph
                    nodes={displayedNodes}
                    edges={displayedEdges}
                    onNodeClick={handleNodeClick}
                    onNodeHover={(id) => {
                      setHoveredNode(id);
                      if (id) {
                        resolvePath(id, displayedNodes, displayedEdges);
                      } else {
                        setPathNodes([]);
                        setPathEdges([]);
                        setPathText('');
                      }
                    }}
                    height="600px"
                    physics={physics}
                    clustering={clustering}
                    labelMode={showLabels}
                    nodeSize={nodeSize}
                    highlightNodeIds={pathNodes}
                    highlightEdgeIds={pathEdges}
                  />
                );
              })()}
              {hoveredNode && (
                <div className="text-xs text-slate-300 bg-[#111827] border border-white/10 rounded px-3 py-2">
                  {pathText || `Hovering ${hoveredNode}`}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      {legend && (
        <div className="flex gap-4 text-xs text-slate-300 items-center">
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#3b82f6] inline-block" /> Entity</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#a855f7] inline-block" /> Metric</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-[#14b8a6] inline-block" /> Dimension</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded-full border border-[#22c55e] inline-block" /> Promoted</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded-full border border-[#ef4444] inline-block" /> Error</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-3 rounded-full border border-[#94a3b8] inline-block" /> Ignored</span>
        </div>
      )}
    </div>
  );
};
