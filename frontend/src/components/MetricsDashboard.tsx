import { Activity, Bot, CircuitBoard, DollarSign, Zap } from "lucide-react";
import type { SystemMetrics } from "../types";

interface Props {
  metrics: SystemMetrics | null;
}

function StatCard({ icon: Icon, label, value, color }: {
  icon: typeof Bot;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 flex items-center gap-3">
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon size={16} className="text-white" />
      </div>
      <div>
        <div className="text-xs text-gray-400">{label}</div>
        <div className="text-sm font-bold text-white">{value}</div>
      </div>
    </div>
  );
}

export default function MetricsDashboard({ metrics }: Props) {
  if (!metrics) return null;

  return (
    <div className="bg-gray-900 border-b border-gray-700 px-4 py-3">
      <div className="flex gap-3 overflow-x-auto">
        <StatCard icon={Bot} label="Active" value={`${metrics.active_agents}/${metrics.total_agents}`} color="bg-blue-600" />
        <StatCard icon={Zap} label="Tokens" value={metrics.total_tokens.toLocaleString()} color="bg-purple-600" />
        <StatCard icon={DollarSign} label="Cost" value={`$${metrics.total_cost_usd.toFixed(4)}`} color="bg-green-600" />
        <StatCard icon={Activity} label="Avg Latency" value={`${metrics.avg_latency_ms.toFixed(0)}ms`} color="bg-yellow-600" />
        <StatCard icon={CircuitBoard} label="Tasks" value={`${metrics.running_tasks} running / ${metrics.pending_tasks} queued`} color="bg-red-600" />
      </div>
    </div>
  );
}
