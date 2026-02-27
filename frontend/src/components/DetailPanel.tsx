import { Play, Square, RotateCcw, Activity } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { Agent, MetricPoint } from "../types";

interface Props {
  agent: Agent | null;
  metrics: MetricPoint[];
  onCommand: (agentId: string, action: string) => void;
}

export default function DetailPanel({ agent, metrics, onCommand }: Props) {
  if (!agent) {
    return (
      <div className="w-80 bg-gray-900 border-l border-gray-700 p-4 flex items-center justify-center text-gray-500">
        Select an agent to view details
      </div>
    );
  }

  return (
    <div className="w-80 bg-gray-900 border-l border-gray-700 p-4 overflow-y-auto">
      <h2 className="text-lg font-bold text-white mb-1">{agent.name}</h2>
      <p className="text-sm text-gray-400 mb-4">{agent.description || agent.type}</p>

      {/* Status + Controls */}
      <div className="flex items-center gap-2 mb-4">
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          agent.status === "working" ? "bg-blue-500/20 text-blue-400" :
          agent.status === "idle" ? "bg-green-500/20 text-green-400" :
          agent.status === "error" ? "bg-red-500/20 text-red-400" :
          "bg-gray-500/20 text-gray-400"
        }`}>
          {agent.status}
        </span>
        <div className="flex gap-1 ml-auto">
          <button onClick={() => onCommand(agent.id, "start")} className="p-1 hover:bg-gray-700 rounded" title="Start">
            <Play size={14} className="text-green-400" />
          </button>
          <button onClick={() => onCommand(agent.id, "stop")} className="p-1 hover:bg-gray-700 rounded" title="Stop">
            <Square size={14} className="text-red-400" />
          </button>
          <button onClick={() => onCommand(agent.id, "restart")} className="p-1 hover:bg-gray-700 rounded" title="Restart">
            <RotateCcw size={14} className="text-yellow-400" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="bg-gray-800 rounded p-2">
          <div className="text-xs text-gray-400">Tokens</div>
          <div className="text-sm font-medium text-white">{(agent.token_count ?? 0).toLocaleString()}</div>
        </div>
        <div className="bg-gray-800 rounded p-2">
          <div className="text-xs text-gray-400">Cost</div>
          <div className="text-sm font-medium text-white">${(agent.total_cost ?? 0).toFixed(4)}</div>
        </div>
      </div>

      {/* Metrics Chart */}
      {metrics.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-gray-300 mb-2 flex items-center gap-1">
            <Activity size={14} /> Latency (ms)
          </h3>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={metrics}>
              <XAxis dataKey="timestamp" hide />
              <YAxis width={40} tick={{ fontSize: 10, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151" }} />
              <Line type="monotone" dataKey="latency" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Model */}
      {agent.model && (
        <div className="text-xs text-gray-400">
          Model: <span className="text-gray-300">{agent.model}</span>
        </div>
      )}
    </div>
  );
}
