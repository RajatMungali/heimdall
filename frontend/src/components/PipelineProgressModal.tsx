import React, { useEffect, useState, useRef } from 'react';
import { Globe, Cpu, Zap, Database, CheckCircle2, Loader2, Terminal, FastForward, X } from 'lucide-react';

interface PipelineProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
  isInline?: boolean;
}

const STAGES = [
  {
    id: 1,
    title: 'Fetching Data',
    subtitle: 'Crawling SERPs, Reddit, X, LinkedIn & Apollo APIs',
    icon: Globe,
    color: 'text-amber-500 dark:text-amber-400',
    borderColor: 'border-amber-500/40',
    bgColor: 'bg-amber-500/10',
    startSec: 0,
    endSec: 60,
  },
  {
    id: 2,
    title: 'LLM Parsing Data',
    subtitle: 'Gemini LLM intent signal extraction & ICP score matrix',
    icon: Cpu,
    color: 'text-emerald-500 dark:text-emerald-400',
    borderColor: 'border-emerald-500/40',
    bgColor: 'bg-emerald-500/10',
    startSec: 60,
    endSec: 135,
  },
  {
    id: 3,
    title: 'Pitch & Trigger Synthesis',
    subtitle: 'Formulating outreach hooks & why-now triggers',
    icon: Zap,
    color: 'text-teal-500 dark:text-teal-400',
    borderColor: 'border-teal-500/40',
    bgColor: 'bg-teal-500/10',
    startSec: 135,
    endSec: 210,
  },
  {
    id: 4,
    title: 'DB Sync & Ingestion',
    subtitle: 'Persisting enriched company records into frontend lead state',
    icon: Database,
    color: 'text-indigo-500 dark:text-indigo-400',
    borderColor: 'border-indigo-500/40',
    bgColor: 'bg-indigo-500/10',
    startSec: 210,
    endSec: 240,
  },
];

const LOG_TEMPLATES = [
  { sec: 2, text: '[SYS_INIT] Initializing multi-source intelligence pipeline...' },
  { sec: 8, text: '[SERP_SCRAPER] Querying Google SERP endpoints for high-growth SaaS signals...' },
  { sec: 18, text: '[SOCIAL_ENGINE] Crawling Reddit & X intent threads for hiring & stack upgrades...' },
  { sec: 32, text: '[APOLLO_API] Fetching headcount growth & executive decision-maker profiles...' },
  { sec: 48, text: '[SCRAPER] Successfully ingested 18 raw company target records.' },
  { sec: 62, text: '[LLM_PARSER] Dispatching raw payload to Gemini LLM for structured extraction...' },
  { sec: 85, text: '[ICP_MATRIX] Computing fit scores: evaluating revenue, tech stack, and SDR hiring...' },
  { sec: 110, text: '[LLM_PARSER] Extracted 6 High Fit (80+), 8 Medium Fit (60-80), 4 Low Fit targets.' },
  { sec: 140, text: '[SYNTHESIZER] Generating personalized why-now triggers & outreach hooks...' },
  { sec: 175, text: '[SYNTHESIZER] Synthesized AI pitch summaries for all verified leads.' },
  { sec: 215, text: '[DB_SYNC] Writing enriched company objects to SQLite database...' },
  { sec: 232, text: '[SYS_COMPLETE] Database transaction committed. Broadcasting state update...' },
];

export default function PipelineProgressModal({ isOpen, onClose, onComplete, isInline = false }: PipelineProgressModalProps) {
  const [elapsedSec, setElapsedSec] = useState(0);
  const [logs, setLogs] = useState<string[]>(['[00:00] [SYS_INIT] Pipeline execution initialized.']);
  const [isFinished, setIsFinished] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const TOTAL_DURATION = 240; // 4 minutes = 240 seconds

  useEffect(() => {
    if (!isOpen) {
      setElapsedSec(0);
      setLogs(['[00:00] [SYS_INIT] Pipeline execution initialized.']);
      setIsFinished(false);
      return;
    }

    const timer = setInterval(() => {
      setElapsedSec((prev) => {
        const next = prev + 1;
        if (next >= TOTAL_DURATION) {
          clearInterval(timer);
          setIsFinished(true);
          onComplete();
          return TOTAL_DURATION;
        }

        // Check if any log template matches current second
        const foundLog = LOG_TEMPLATES.find((l) => l.sec === next);
        if (foundLog) {
          const mins = Math.floor(next / 60).toString().padStart(2, '0');
          const secs = (next % 60).toString().padStart(2, '0');
          setLogs((prevLogs) => [...prevLogs, `[${mins}:${secs}] ${foundLog.text}`]);
        }

        return next;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  if (!isOpen) return null;

  const currentStageIndex = STAGES.findIndex(
    (s) => elapsedSec >= s.startSec && elapsedSec < s.endSec
  );
  const activeStage = STAGES[currentStageIndex >= 0 ? currentStageIndex : STAGES.length - 1];

  const progressPercent = Math.min(100, Math.round((elapsedSec / TOTAL_DURATION) * 100));

  const formatMinSec = (totalSeconds: number) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const remainingSec = Math.max(0, TOTAL_DURATION - elapsedSec);

  const cardContent = (
    <div className={`relative w-full ${isInline ? 'rounded-3xl border border-slate-200 dark:border-nexa-border bg-white dark:bg-[#12121a] p-5 shadow-sm text-left' : 'nexa-card max-w-2xl rounded-3xl border border-slate-200 dark:border-nexa-border bg-white dark:bg-[#12121a] p-6 shadow-2xl overflow-hidden max-h-[90vh] text-left'} flex flex-col`}>
      
      {/* Top Header Bar */}
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-white/10 pb-4 mb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
            <Loader2 size={20} className="animate-spin" />
          </div>
          <div>
            <h2 className="text-base font-black text-slate-900 dark:text-zinc-100 flex items-center gap-2">
              Pipeline Execution Engine
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-400/30">
                Live Sweep
              </span>
            </h2>
            <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium mt-0.5">
              Automated Intent Crawl, LLM Extraction & Lead Enrichment
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Unclickable Fast Forward Option as requested by user */}
          <button
            type="button"
            disabled
            title="Fast-forward option is disabled during active live execution"
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-3 py-1.5 text-xs font-bold text-slate-400 dark:text-zinc-500 opacity-60 cursor-not-allowed"
          >
            <FastForward size={14} />
            <span>Fast-Forward</span>
          </button>

          {isFinished && !isInline && (
            <button
              type="button"
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-100 dark:bg-white/10 text-slate-600 dark:text-zinc-300 hover:text-slate-950 dark:hover:text-white transition"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Global Progress Bar & Timer */}
      <div className="mb-6 bg-slate-50 dark:bg-white/5 p-4 rounded-2xl border border-slate-200/80 dark:border-white/5">
        <div className="flex items-center justify-between mb-2 text-xs">
          <span className="font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            Overall Progress
            <span className="text-emerald-600 dark:text-emerald-400 font-extrabold">{progressPercent}%</span>
          </span>
          <span className="font-mono text-slate-500 dark:text-zinc-400 font-bold">
            {formatMinSec(elapsedSec)} / 4:00 (Est. {formatMinSec(remainingSec)} remaining)
          </span>
        </div>

        {/* Animated Track */}
        <div className="h-2.5 w-full rounded-full bg-slate-200 dark:bg-zinc-800 overflow-hidden relative">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-amber-400 transition-all duration-500 ease-linear rounded-full relative"
            style={{ width: `${progressPercent}%` }}
          >
            <div className="absolute inset-0 bg-white/20 animate-pulse" />
          </div>
        </div>
      </div>

      {/* 4 Stage Timeline Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
        {STAGES.map((stage) => {
          const Icon = stage.icon;
          const isPast = elapsedSec >= stage.endSec;
          const isCurrent = elapsedSec >= stage.startSec && elapsedSec < stage.endSec;

          return (
            <div
              key={stage.id}
              className={`flex items-start gap-3 p-3 rounded-2xl border transition-all duration-300 ${
                isCurrent
                  ? `${stage.borderColor} ${stage.bgColor} shadow-sm ring-1 ring-emerald-500/30`
                  : isPast
                  ? 'border-emerald-500/30 bg-emerald-500/5'
                  : 'border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/5 opacity-50'
              }`}
            >
              <div
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
                  isPast
                    ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-500 dark:text-emerald-400'
                    : isCurrent
                    ? `${stage.borderColor} ${stage.bgColor} ${stage.color}`
                    : 'border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-white/5 text-slate-400 dark:text-zinc-500'
                }`}
              >
                {isPast ? (
                  <CheckCircle2 size={18} className="text-emerald-500" />
                ) : isCurrent ? (
                  <Icon size={18} className={`${stage.color} animate-pulse`} />
                ) : (
                  <Icon size={18} />
                )}
              </div>

              <div className="flex flex-col text-left">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-black ${isCurrent ? 'text-slate-900 dark:text-zinc-100' : isPast ? 'text-slate-700 dark:text-zinc-300' : 'text-slate-500 dark:text-zinc-500'}`}>
                    Stage {stage.id}: {stage.title}
                  </span>
                  {isCurrent && (
                    <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-ping" />
                  )}
                </div>
                <span className="text-[11px] text-slate-500 dark:text-zinc-400 font-medium leading-tight mt-0.5">
                  {stage.subtitle}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Terminal Log Console */}
      <div className="flex-1 min-h-[140px] max-h-[180px] rounded-2xl border border-slate-200 dark:border-white/10 bg-slate-950 p-3.5 font-mono text-xs text-emerald-400 shadow-inner flex flex-col justify-between overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2">
          <div className="flex items-center gap-2 text-slate-400 text-[11px] font-bold">
            <Terminal size={14} className="text-emerald-400" />
            <span>LIVE PIPELINE LOGS</span>
          </div>
          <span className="text-[10px] text-slate-500">Auto-scrolling</span>
        </div>

        <div className="flex-1 overflow-y-auto space-y-1 pr-1 scrollbar-thin text-[11px]">
          {logs.map((log, i) => (
            <div key={i} className="leading-relaxed">
              <span className="text-emerald-400">{log}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>

      {/* Bottom Action Controls */}
      <div className="mt-5 flex items-center justify-between pt-2 border-t border-slate-100 dark:border-white/10">
        <span className="text-xs font-bold text-slate-500 dark:text-zinc-400 flex items-center gap-1.5">
          {isFinished ? (
            <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-black">
              <CheckCircle2 size={15} /> Execution Complete — State Ingested!
            </span>
          ) : (
            <span className="flex items-center gap-1.5">
              <Loader2 size={14} className="animate-spin text-emerald-500" />
              Pipeline running in background…
            </span>
          )}
        </span>

        {isFinished && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white shadow-md hover:bg-emerald-500 transition"
          >
            View Enriched Companies
          </button>
        )}
      </div>

    </div>
  );

  if (isInline) return cardContent;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 dark:bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
      {cardContent}
    </div>
  );
}
