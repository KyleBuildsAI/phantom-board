export type AgentStatus = "idle" | "working" | "stopped" | "error" | "starting" | "stopping";
export type AgentType = "llm" | "tool" | "orchestrator" | "worker" | "router" | "custom";
export type TaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface Agent {
  id: string;
  name: string;
  type: AgentType;
  status: AgentStatus;
  description?: string;
  model?: string;
  position_x: number;
  position_y: number;
  token_count?: number;
  total_cost?: number;
  current_task?: string;
}

export interface Task {
  id: string;
  description: string;
  status: TaskStatus;
  agent_id?: string;
  priority: number;
  created_at: string;
  duration_seconds?: number;
}

export interface MetricPoint {
  timestamp: string;
  tokens: number;
  cost: number;
  latency: number;
  cpu: number;
  memory: number;
}

export interface SystemMetrics {
  total_agents: number;
  active_agents: number;
  idle_agents: number;
  error_agents: number;
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
}

export interface Connection {
  source: string;
  target: string;
  message_count: number;
  active?: boolean;
}

export interface WSEvent {
  event: string;
  data: Record<string, unknown>;
  timestamp: string;
}
