import { useState, useCallback } from "react";
import AgentCanvas from "./components/AgentCanvas";
import DetailPanel from "./components/DetailPanel";
import MetricsDashboard from "./components/MetricsDashboard";
import TaskQueue from "./components/TaskQueue";
import { useWebSocket } from "./hooks/useWebSocket";
import type { Agent, Task, MetricPoint, SystemMetrics, Connection } from "./types";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

export default function App() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentMetrics, setAgentMetrics] = useState<Record<string, MetricPoint[]>>({});

  const handleMessage = useCallback((event: { type: string; data: unknown }) => {
    switch (event.type) {
      case "agent_update": {
        const agent = event.data as Agent;
        setAgents((prev) => {
          const idx = prev.findIndex((a) => a.id === agent.id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = agent;
            return next;
          }
          return [...prev, agent];
        });
        break;
      }
      case "agent_removed": {
        const { agent_id } = event.data as { agent_id: string };
        setAgents((prev) => prev.filter((a) => a.id !== agent_id));
        if (selectedAgentId === agent_id) setSelectedAgentId(null);
        break;
      }
      case "task_update": {
        const task = event.data as Task;
        setTasks((prev) => {
          const idx = prev.findIndex((t) => t.id === task.id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = task;
            return next;
          }
          return [...prev, task];
        });
        break;
      }
      case "metrics": {
        const point = event.data as MetricPoint & { agent_id: string };
        setAgentMetrics((prev) => {
          const existing = prev[point.agent_id] || [];
          return {
            ...prev,
            [point.agent_id]: [...existing.slice(-59), point],
          };
        });
        break;
      }
      case "system_metrics": {
        setSystemMetrics(event.data as SystemMetrics);
        break;
      }
      case "connections": {
        setConnections(event.data as Connection[]);
        break;
      }
      case "snapshot": {
        const snap = event.data as {
          agents: Agent[];
          tasks: Task[];
          connections: Connection[];
          system_metrics: SystemMetrics;
        };
        setAgents(snap.agents);
        setTasks(snap.tasks);
        setConnections(snap.connections);
        setSystemMetrics(snap.system_metrics);
        break;
      }
    }
  }, [selectedAgentId]);

  const { connected, send } = useWebSocket(WS_URL, handleMessage);

  const handleCommand = useCallback(
    (agentId: string, action: string) => {
      send({ type: "command", data: { agent_id: agentId, action } });
    },
    [send]
  );

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) || null;
  const selectedMetrics = selectedAgentId ? agentMetrics[selectedAgentId] || [] : [];

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-white">
      {/* Connection indicator */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
        <h1 className="text-lg font-bold tracking-tight">Phantom Board</h1>
        <div className="flex items-center gap-2 text-xs">
          <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400 animate-pulse"}`} />
          <span className="text-gray-400">{connected ? "Connected" : "Disconnected"}</span>
          <span className="text-gray-600 ml-2">{agents.length} agents</span>
        </div>
      </div>

      {/* Metrics bar */}
      <MetricsDashboard metrics={systemMetrics} />

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        <AgentCanvas
          agents={agents}
          connections={connections}
          onSelectAgent={setSelectedAgentId}
        />
        <DetailPanel
          agent={selectedAgent}
          metrics={selectedMetrics}
          onCommand={handleCommand}
        />
      </div>

      {/* Task queue */}
      <TaskQueue tasks={tasks} />
    </div>
  );
}
