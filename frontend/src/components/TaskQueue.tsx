import { Clock, CheckCircle, XCircle, Loader } from "lucide-react";
import type { Task, TaskStatus } from "../types";

const STATUS_CONFIG: Record<TaskStatus, { icon: typeof Clock; color: string }> = {
  pending: { icon: Clock, color: "text-gray-400" },
  running: { icon: Loader, color: "text-blue-400" },
  completed: { icon: CheckCircle, color: "text-green-400" },
  failed: { icon: XCircle, color: "text-red-400" },
  cancelled: { icon: XCircle, color: "text-gray-500" },
};

interface Props {
  tasks: Task[];
}

export default function TaskQueue({ tasks }: Props) {
  return (
    <div className="bg-gray-900 border-t border-gray-700 p-3 max-h-48 overflow-y-auto">
      <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Task Queue</h3>
      {tasks.length === 0 ? (
        <p className="text-xs text-gray-500">No tasks</p>
      ) : (
        <div className="space-y-1">
          {tasks.slice(0, 20).map((task) => {
            const cfg = STATUS_CONFIG[task.status];
            const Icon = cfg.icon;
            return (
              <div key={task.id} className="flex items-center gap-2 text-xs py-1 px-2 rounded hover:bg-gray-800">
                <Icon size={12} className={cfg.color} />
                <span className="text-gray-300 truncate flex-1">{task.description}</span>
                <span className="text-gray-500">{task.agent_id?.slice(0, 6) || "unassigned"}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
