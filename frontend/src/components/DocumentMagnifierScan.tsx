import { Search, Sparkles, FileText, Lock } from 'lucide-react';
import { motion } from 'framer-motion';

const BLURRED_NAMES = [
  'Acme Global Dynamics Inc. — $12.5M Series A',
  'TechCorp Synthetics LLC — Hiring 6 SDRs',
  'Vortex Intelligence Systems — SBIR Grant Win',
  'OmniData AI Technologies — Executive Hire',
  'Hyperion Cybernetics Corp — Scaling Sales',
  'Starlight Cloud Platforms — Series B Funding',
  'Nexus BioTech Enterprise — DoD Contract',
  'Apex Scale Labs — Hiring 8 SDRs & AEs',
  'QuantumPulse Systems — $2.5M Seed Round',
  'Cipher Core Software — Expansion Mode',
  'Aetherial Data Labs — Vice President Hire',
  'Vector Prime Automation — Outbound Push',
];

export default function DocumentMagnifierScan() {
  // Duplicate array to ensure seamless infinite looping animation
  const doubledNames = [...BLURRED_NAMES, ...BLURRED_NAMES];

  return (
    <div className="flex flex-col items-center justify-center p-2 sm:p-4 w-full my-auto">
      {/* Outer Canvas Container */}
      <div className="relative flex items-center justify-center w-full max-w-[460px] sm:max-w-[520px] shrink-0">
        
        {/* Subtle Ambient Glow behind Sheet */}
        <div className="absolute inset-2 rounded-[2.5rem] bg-slate-400/20 dark:bg-zinc-800/30 blur-3xl animate-pulse pointer-events-none" />

        {/* 1. CENTRAL DOCUMENT SHEET — Wider & Shorter Aspect Ratio */}
        <motion.div
          initial={{ scale: 0.94, opacity: 0, y: 10 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 220, damping: 22 }}
          className="relative w-[360px] h-[320px] sm:w-[440px] sm:h-[360px] rounded-2xl border-2 border-slate-900 dark:border-zinc-700 bg-white text-zinc-950 shadow-[0_20px_50px_-10px_rgba(0,0,0,0.18)] dark:shadow-[0_25px_60px_-15px_rgba(0,0,0,0.45)] p-5 flex flex-col justify-between overflow-hidden z-10 shrink-0"
        >
          {/* Subtle Paper Top Bar */}
          <div className="absolute top-0 inset-x-0 h-1.5 bg-slate-900 dark:bg-zinc-700 shrink-0 z-30" />

          {/* Top Document Header Bar */}
          <div className="flex items-center justify-between pb-3 border-b-2 border-slate-900 dark:border-zinc-700 shrink-0 mt-0.5 z-30 bg-white">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-900 dark:bg-zinc-800 text-white shadow-sm">
                <FileText size={14} />
              </div>
              <div className="flex flex-col">
                <span className="text-[11px] font-black tracking-wider uppercase font-mono text-slate-900 leading-none">
                  INTENT_REPORT.PDF
                </span>
                <span className="text-[8px] font-mono font-semibold text-slate-500 tracking-tight mt-0.5">
                  FORM A4-LIVE-DISCOVERY
                </span>
              </div>
            </div>
          </div>

          {/* Laser Scanning Line Sweep */}
          <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-slate-700/60 dark:via-zinc-400/60 to-transparent shadow-[0_0_12px_rgba(0,0,0,0.25)] animate-laser-sweep pointer-events-none z-20" />

          {/* Middle Body: Scrolling Blurred Company & Intent Records */}
          <div className="relative flex-1 my-3 overflow-hidden rounded-xl bg-slate-50 border border-slate-200 p-2.5 shadow-inner">
            {/* Top & Bottom gradient mask for smooth fade out */}
            <div className="absolute inset-x-0 top-0 h-8 bg-gradient-to-b from-slate-50 to-transparent z-10 pointer-events-none" />
            <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-slate-50 to-transparent z-10 pointer-events-none" />

            {/* Vertical Infinite Scroll Track */}
            <div className="animate-scroll-blurred flex flex-col gap-2">
              {doubledNames.map((name, idx) => (
                <div
                  key={`${name}-${idx}`}
                  className="flex items-center justify-between py-1.5 px-2.5 rounded-lg bg-white border border-slate-200/90 shadow-2xs select-none"
                >
                  <span className="text-[11px] font-extrabold text-slate-900 tracking-tight font-mono blur-[3.2px] transition-all">
                    {name}
                  </span>
                  <div className="w-10 h-2 rounded bg-slate-800/80 blur-[1.5px] shrink-0" />
                </div>
              ))}
            </div>

            {/* 2. REVOLVING MAGNIFYING GLASS (INSIDE THE DOCUMENT BODY) */}
            <div className="absolute left-1/2 top-1/2 animate-inner-magnifier z-30 pointer-events-none">
              <div className="relative flex items-center justify-center w-20 h-20 sm:w-22 sm:h-22 rounded-full bg-white/95 border-3 border-slate-900 shadow-[0_12px_35px_rgba(0,0,0,0.25)] backdrop-blur-[0.5px]">
                {/* Lens glare highlight */}
                <div className="absolute inset-1 rounded-full bg-gradient-to-tr from-transparent via-slate-200/60 to-transparent pointer-events-none" />
                
                {/* Upright Magnifying Search Icon */}
                <Search size={30} className="text-slate-900 stroke-[2.75] animate-pulse relative z-10" />

                {/* Micro Live Status Dot */}
                <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-slate-900 border-2 border-white flex items-center justify-center">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                </div>
              </div>
            </div>
          </div>

          {/* Document Footer Bar */}
          <div className="pt-2.5 border-t-2 border-slate-900 dark:border-zinc-700 flex items-center justify-between shrink-0 text-[10px] font-mono text-slate-900 font-bold z-30 bg-white">
            <span className="flex items-center gap-1">
              <Sparkles size={12} className="text-slate-900" /> MULTI-SOURCE INTENT
            </span>
            <span className="px-2 py-0.5 rounded-md bg-slate-900 dark:bg-zinc-800 text-white font-black text-[9px] tracking-wider">
              LIVE CRAWL
            </span>
          </div>
        </motion.div>

      </div>

      {/* Status Text & Indicator below A4 Animation Canvas */}
      <div className="mt-4 flex flex-col items-center gap-2 text-center z-10">
        <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-900 dark:bg-zinc-900 border border-slate-800 dark:border-zinc-800 text-white text-xs font-bold font-mono shadow-xl">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>Pipeline Intent Discovery Active</span>
        </div>
        <p className="text-xs text-slate-600 dark:text-zinc-400 font-medium max-w-sm">
          Searching Exa AI, Google SERPs, Reddit, X & Apollo APIs for buyer intent signals...
        </p>
      </div>
    </div>
  );
}
