import React from 'react';
import { Network, Activity, Cpu, Database, Binary, Zap } from 'lucide-react';

export default function AgentTrace({ traceLog, domain }) {
  if (!traceLog || traceLog.length === 0) {
    return (
      <div className="empty-state">
        <Activity size={48} opacity={0.2} />
        <p>No agent activity yet.</p>
      </div>
    );
  }

  const getIconForDomain = (domainStr) => {
    switch (domainStr) {
      case 'compiler_theory': return <Cpu size={18} color="var(--accent-purple)" />;
      case 'algorithms': return <Network size={18} color="var(--accent-blue)" />;
      case 'theory_of_comp': return <Binary size={18} color="var(--accent-teal)" />;
      default: return <Database size={18} color="var(--accent-green)" />;
    }
  };

  return (
    <div className="trace-content">
      {traceLog.map((log, index) => {
        // Parse the raw log (e.g., "[Router] Classified query into domain 'compiler_theory' ...")
        const isRouter = log.startsWith("[Router]");
        const agentName = isRouter ? "Router Agent" : "Domain Specialist";
        const icon = isRouter ? <Zap size={18} color="#eab308" /> : getIconForDomain(domain);
        
        // Remove the bracketed prefix for cleaner display
        const text = log.replace(/^\[.*?\]\s*/, '');

        return (
          <div key={index} className="trace-step">
            <div className="trace-icon">
              {icon}
            </div>
            <div className="trace-details">
              <div className="trace-agent-name">{agentName}</div>
              <div className="trace-text">{text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
