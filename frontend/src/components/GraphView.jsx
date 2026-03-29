import React, { useEffect, useRef, useState } from 'react';
import { ReactFlow, useNodesState, useEdgesState, Background, Controls, MarkerType } from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { Search, Loader2, GitMerge } from 'lucide-react';
import { getUserGraph } from '../api';
import toast from 'react-hot-toast';
import UserSearchCombobox from './UserSearchCombobox';

const getLayoutedElements = (nodes, edges, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ 
    rankdir: direction,
    nodesep: 80,   // Horizontal spacing between nodes
    ranksep: 120,  // Vertical spacing between ranks
    marginx: 40,
    marginy: 40
  });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 180, height: 85 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: direction === 'TB' ? 'top' : 'left',
      sourcePosition: direction === 'TB' ? 'bottom' : 'right',
      position: {
        x: nodeWithPosition.x - 90,
        y: nodeWithPosition.y - 42.5,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

const CustomNode = ({ data }) => {
  const isFlagged = data.status === 'flagged';
  const isRoot = data.status === 'root';

  let layoutClasses = 'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 hover:border-cyan-500/50 hover:shadow-cyan-500/10 transition-all';
  if (isFlagged) {
    layoutClasses = 'bg-rose-50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900/50 text-rose-900 dark:text-rose-200';
  } else if (isRoot) {
    layoutClasses = 'bg-indigo-50 dark:bg-indigo-950/30 border-indigo-200 dark:border-indigo-900/50 text-indigo-900 dark:text-indigo-200';
  }

  return (
    <div className={`px-5 py-4 rounded-xl border shadow-sm flex flex-col items-center justify-center min-w-[180px] group ${layoutClasses}`} title={data.user_id}>
      <span className="font-semibold text-[15px] tracking-tight truncate w-full text-center">{data.username}</span>
      <span className="text-[11px] font-mono text-zinc-500 dark:text-zinc-400 tracking-wider mt-1.5 uppercase opacity-80 group-hover:opacity-100 transition-opacity">{(data.user_id || '').substring(0, 8)}</span>
      
      {isFlagged && <span className="absolute -top-2.5 -right-2.5 bg-rose-100 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 text-rose-600 dark:text-rose-400 text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-widest shadow-sm">Flagged</span>}
      {isRoot && <span className="absolute -top-2.5 -right-2.5 bg-indigo-100 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-indigo-600 dark:text-indigo-400 text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-widest shadow-sm">Root</span>}
    </div>
  );
};

const nodeTypes = { custom: CustomNode };

const GraphView = ({ selectedUserId, selectionSource }) => {
  const [userId, setUserId] = useState('');
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(false);
  const [emptyMsg, setEmptyMsg] = useState('Pick a user from Fraud Monitor or enter a full UUID to view their referral tree.');
  const lastLoadedRef = useRef('');

  const buildGraphElements = (treeNode) => {
    const newNodes = [];
    const newEdges = [];

    const traverse = (node, parentId = null) => {
      newNodes.push({
        id: node.user_id,
        type: 'custom',
        position: { x: 0, y: 0 },
        data: { username: node.username, status: node.status, user_id: node.user_id },
      });

      if (parentId) {
        newEdges.push({
          id: `e-${parentId}-${node.user_id}`,
          source: parentId,
          target: node.user_id,
          type: 'smoothstep',
          animated: node.status === 'active',
          style: { 
            stroke: node.status === 'flagged' ? 'rgba(244, 63, 94, 0.6)' : 'rgba(161, 161, 170, 0.6)', 
            strokeWidth: 2 
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 15,
            height: 15,
            color: node.status === 'flagged' ? 'rgba(244, 63, 94, 0.6)' : 'rgba(161, 161, 170, 0.6)',
          },
        });
      }
      (node.children || []).forEach((child) => traverse(child, node.user_id));
    };

    traverse(treeNode);
    return { newNodes, newEdges };
  };

  const loadGraph = async (targetUserId, source = '') => {
    if (!targetUserId?.trim()) return;

    setLoading(true);
    setEmptyMsg('');
    try {
      const data = await getUserGraph(targetUserId.trim());
      if (!data || !data.tree) {
        setNodes([]);
        setEdges([]);
        setEmptyMsg('User found but has no active DAG tree.');
        return;
      }
      const { newNodes, newEdges } = buildGraphElements(data.tree);
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(newNodes, newEdges);
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
      setUserId(targetUserId.trim());
      lastLoadedRef.current = targetUserId.trim();
      if (newNodes.length === 1) {
        setEmptyMsg('This user has no downstream referrals yet.');
      }
      if (source) {
        toast.success(`Loaded ${source} user in DAG Explorer`);
      }
    } catch (error) {
      setNodes([]);
      setEdges([]);
      if (error.response?.status === 404) {
        setEmptyMsg('User not found in system.');
        toast.error('User not found');
      } else {
        setEmptyMsg('Failed to load graph. Backend might be down.');
        toast.error('Graph load failed.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedUserId && selectedUserId !== lastLoadedRef.current) {
      loadGraph(selectedUserId, selectionSource);
    }
  }, [selectedUserId, selectionSource]);

  return (
    <div className="saas-card flex flex-col h-[600px] relative overflow-hidden">
      <div className="p-6 border-b border-zinc-200 dark:border-zinc-800/60 bg-white dark:bg-zinc-950/80 backdrop-blur flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 z-10 w-full relative">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 flex items-center justify-center">
            <GitMerge className="w-4 h-4 text-zinc-500 dark:text-zinc-400 transform -rotate-90" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">DAG Explorer</h2>
            <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-widest mt-0.5">Referral Topography</p>
          </div>
        </div>

        <div className="flex gap-2 w-full sm:w-80 relative">
          <UserSearchCombobox
            value={userId}
            onChange={(id) => {
              setUserId(id);
              loadGraph(id);
            }}
            className="w-full bg-white dark:bg-zinc-900"
            placeholder="Search username, email or UUID..."
          />
        </div>
      </div>

      <div className="flex-1 w-full relative bg-zinc-50 dark:bg-zinc-950 bg-grid-pattern">
        {nodes.length > 0 ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-right"
            className="react-flow-dark"
          >
            <Background gap={24} size={1} className="dark:opacity-50" />
            <Controls showInteractive={false} className="opacity-50 hover:opacity-100 transition-opacity bg-white dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700" />
          </ReactFlow>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none p-6 text-center">
            <div className="w-16 h-16 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/50 flex items-center justify-center mb-4 shadow-sm">
              <GitMerge className="w-6 h-6 text-zinc-400 dark:text-zinc-600" />
            </div>
            <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">{emptyMsg}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphView;
