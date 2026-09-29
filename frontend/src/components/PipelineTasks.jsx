import React from 'react';
import { ListChecks, CheckCircle2, XCircle, Clock } from 'lucide-react';

export default function PipelineTasks({ tasks }) {
  if (!tasks || tasks.length === 0) return null;

  const calculateDuration = (started, completed) => {
    if (!started || !completed) return '—';
    const start = new Date(started).getTime();
    const end = new Date(completed).getTime();
    const diff = (end - start) / 1000;
    return `${diff.toFixed(2)}s`;
  };

  return (
    <div className="pipeline-tasks-card">
      <div className="tasks-header">
        <div className="tasks-title">
          <ListChecks size={18} style={{ marginRight: '6px' }} />
          Pipeline Execution Tasks (7 Sequential Stages)
        </div>
        <span className="tasks-subtitle">Recorded in PostgreSQL table: <code>pipeline_tasks</code></span>
      </div>

      <div className="table-responsive">
        <table className="enterprise-table tasks-table">
          <thead>
            <tr>
              <th style={{ width: '50px' }}>#</th>
              <th>Task Stage</th>
              <th style={{ width: '130px' }}>Status</th>
              <th style={{ width: '130px' }}>Rows In</th>
              <th style={{ width: '130px' }}>Rows Out</th>
              <th style={{ width: '100px' }}>Duration</th>
              <th>Error Details</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task, idx) => (
              <tr key={task.id || idx}>
                <td className="row-num">{idx + 1}</td>
                <td className="task-name">
                  <strong>{task.task_name}</strong>
                </td>
                <td>
                  <span className={`badge ${task.status === 'SUCCESS' ? 'badge-success' : task.status === 'FAILED' ? 'badge-danger' : 'badge-neutral'}`}>
                    {task.status === 'SUCCESS' && <CheckCircle2 size={12} style={{ marginRight: '4px' }} />}
                    {task.status === 'FAILED' && <XCircle size={12} style={{ marginRight: '4px' }} />}
                    {task.status === 'RUNNING' && <Clock size={12} style={{ marginRight: '4px' }} />}
                    {task.status}
                  </span>
                </td>
                <td className="font-mono">{task.rows_input.toLocaleString()}</td>
                <td className="font-mono">{task.rows_output.toLocaleString()}</td>
                <td className="font-mono">{calculateDuration(task.started_at, task.completed_at)}</td>
                <td className="task-err-cell">
                  {task.error_message ? (
                    <span className="text-danger">{task.error_message}</span>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
