import { useEffect, useState } from 'react';

const MESSAGES = [
  { text: "INITIALIZING NEURAL LINK...", type: "sys" },
  { text: "ESTABLISHING SECURE CONNECTION TO TARGET...", type: "sys" },
  { text: "BYPASSING PERIMETER DEFENSES...", type: "sys" },
  { text: '{"task": "extract_intent", "target": "domain", "status": "active"}', type: "json" },
  { text: "EXTRACTING INTENT SIGNALS...", type: "sys" },
  { text: '{"signal_1": "fundraising", "confidence": 0.92, "source": "news_api"}', type: "json" },
  { text: "ANALYZING DOMAIN DNS HEALTH...", type: "sys" },
  { text: '{"mx_records": "found", "dmarc": "valid", "spf": "pass"}', type: "json" },
  { text: "CROSS-REFERENCING FIRMOGRAPHICS...", type: "sys" },
  { text: '{"employee_count": 145, "industry": "SaaS", "icp_fit": "Strong"}', type: "json" },
  { text: "RUNNING LLM SCORING ALGORITHMS...", type: "sys" },
  { text: '{"model": "gemini-1.5-pro", "tokens": 1420, "temperature": 0.1}', type: "json" },
  { text: "COMPILING FINAL REPORT...", type: "sys" },
  { text: '{"status": "complete", "ready_for_ingestion": true}', type: "json" },
];

export default function HackerScanAnimation({ targetDomain }: { targetDomain: string }) {
  const [logs, setLogs] = useState<{ text: string, type: string }[]>([]);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let currentIndex = 0;
    const interval = setInterval(() => {
      if (currentIndex < MESSAGES.length) {
        setLogs(prev => [...prev, MESSAGES[currentIndex]]);
        setProgress(Math.floor(((currentIndex + 1) / MESSAGES.length) * 100));
        currentIndex++;
      } else {
        clearInterval(interval);
      }
    }, 350); // 350ms * 14 messages = ~4.9 seconds total

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-nexa-bg/95 backdrop-blur-md p-6 font-mono overflow-hidden rounded-xl border border-[var(--nexa-border)]">
      <div className="w-full h-full border border-emerald-500/20 bg-black/60 p-6 rounded-lg shadow-[0_0_30px_rgba(16,185,129,0.1)] flex flex-col relative">
        <div className="flex justify-between items-center border-b border-emerald-500/30 pb-4 mb-4">
          <span className="text-emerald-400 font-bold tracking-widest">HEIMDALL // TARGET ACQUISITION SYSTEM</span>
          <span className="text-emerald-300 bg-emerald-500/10 px-3 py-1 rounded">TARGET: {(targetDomain || "UNKNOWN").toUpperCase()}</span>
        </div>
        
        <div className="flex-1 overflow-y-auto space-y-3 mb-4">
          {logs.map((log, i) => (
            <div key={i} className="animate-fade-in flex gap-4 text-sm">
              <span className="text-emerald-700">[{new Date().toISOString().split('T')[1].slice(0,-1)}]</span>
              {log?.type === 'json' ? (
                <span className="text-amber-400 drop-shadow-[0_0_5px_rgba(251,191,36,0.3)]">{log?.text}</span>
              ) : (
                <span className="text-emerald-400 drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]">{log?.text || (typeof log === 'string' ? log : '')}</span>
              )}
            </div>
          ))}
          <div className="animate-pulse text-emerald-400 drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]">_</div>
        </div>

        <div className="mt-auto pt-4 border-t border-emerald-500/20">
          <div className="flex justify-between text-xs mb-2 text-emerald-400/80">
            <span>EXTRACTION PROGRESS</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1 w-full bg-emerald-950 rounded-full overflow-hidden">
            <div 
              className="h-full bg-emerald-500 transition-all duration-300 shadow-[0_0_10px_#10b981]"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
