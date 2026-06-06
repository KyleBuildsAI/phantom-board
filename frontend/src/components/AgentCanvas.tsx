import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import AgentNode from "./AgentNode";
import type { Agent, Connection } from "../types";

interface Props {
  agents: Agent[];
  connections: Connection[];
  onSelectAgent: (id: string) => void;
}

const nodeTypes = { agent: AgentNode };

export default function AgentCanvas({ agents, connections, onSelectAgent }: Props) {
  const nodes: Node[] = useMemo(
    () =>
      agents.map((a, i) => ({
        id: a.id,
        type: "agent",
        position: { x: a.position_x || (i % 4) * 250 + 50, y: a.position_y || Math.floor(i / 4) * 150 + 50 },
        data: a as unknown as Record<string, unknown>,
      })),
    [agents]
  );

  const edges: Edge[] = useMemo(
    () =>
      connections.map((c, i) => ({
        id: `e-${i}`,
        source: c.source,
        target: c.target,
        animated: c.active,
        style: { stroke: c.active ? "#3b82f6" : "#4b5563" },
        label: c.message_count > 0 ? `${c.message_count}` : undefined,
      })),
    [connections]
  );

  const [nodesState, , onNodesChange] = useNodesState(nodes);
  const [edgesState] = useEdgesState(edges);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => onSelectAgent(node.id),
    [onSelectAgent]
  );

  return (
    <div className="flex-1 h-full">
      <ReactFlow
        nodes={nodesState}
        edges={edgesState}
        onNodesChange={onNodesChange}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#374151" gap={20} />
        <Controls className="!bg-gray-800 !border-gray-600" />
        <MiniMap
          nodeColor={(n) => {
            const s = (n.data as unknown as Agent)?.status;
            if (s === "working") return "#3b82f6";
            if (s === "error") return "#ef4444";
            if (s === "idle") return "#10b981";
            return "#6b7280";
          }}
          className="!bg-gray-900 !border-gray-600"
        />
      </ReactFlow>
    </div>
  );
}
