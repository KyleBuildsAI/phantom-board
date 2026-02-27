import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Bot, Cpu, Network, Wrench, Zap } from "lucide-react";
import type { Agent, AgentStatus } from "../types";

const STATUS_COLORS: Record<AgentStatus, string> = {
  idle: "bg-emerald-400",
  working: "bg-blue-400 animate-pulse",
  stopped: "bg-gray-500",
  error: "bg-red-500",
  starting: "bg-yellow-400 animate-pulse",
  stopping: "bg-orange-400",
};

const TYPE_ICONS: Record<string, typeof Bot> = {
  llm: Bot,
  orchestrator: Network,
  worker: Wrench,
  tool: Cpu,
  router: Zap,
};

function AgentNode({ data }: NodeProps) {
  const agent = data as unknown as Agent;
  const Icon = TYPE_ICONS[agent.type] || Bot;
  const statusColor = STATUS_COLORS[agent.status] || "bg-gray-400";

  return (
    <div className="bg-gray-800 border border-gray-600 rounded-lg p-3 min-w-[180px] shadow-lg hover:border-blue-500 transition-colors">
      <Handle type="target" position={Position.Left} className="!bg-blue-500" />

      <div className="flex items-center gap-2 mb-2">
        <div className={`w-2.5 h-2.5 rounded-full ${statusColor}`} />
        <Icon size={14} className="text-gray-400" />
        <span className="text-sm font-medium text-white truncate">{agent.name}</span>
      </div>

      <div className="text-xs text-gray-400 space-y-1">
        {agent.current_task && (
          <div className="truncate text-blue-300">{agent.current_task}</div>
        )}
        <div className="flex justify-between">
          <span>{agent.token_count?.toLocaleString() ?? 0} tokens</span>
          <span>${(agent.total_cost ?? 0).toFixed(4)}</span>
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-blue-500" />
    </div>
  );
}

export default memo(AgentNode);
