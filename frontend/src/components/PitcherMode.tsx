import { Check, Clipboard, Loader2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchPitcherMode, type PitcherModeResponse } from '../lib/api';

function parseMarkdown(text: string) {
  return text.split('\n').map((line, idx) => {
    let formatted = line;
    // Replace **bold** with <strong>bold</strong>
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong class="text-slate-900 dark:text-zinc-200 font-bold">$1</strong>');
    
    if (line.trim().startsWith('* ') || line.trim().startsWith('- ')) {
      return (
        <li key={idx} className="mb-2 ml-4 list-disc marker:text-[var(--nexa-accent)] text-slate-800 dark:text-zinc-300 font-medium" dangerouslySetInnerHTML={{ __html: formatted.replace(/^[-*]\s/, '') }} />
      );
    }
    return <p key={idx} className="mb-2 text-slate-800 dark:text-zinc-300 font-medium" dangerouslySetInnerHTML={{ __html: formatted }} />;
  });
}

interface PitcherModeProps {
  id: string;
  company_name: string;
  onClose: () => void;
  inline?: boolean;
}

export default function PitcherMode({ id, company_name, onClose, inline = false }: PitcherModeProps) {
  const [loading, setLoading] = useState(true);
  const [pitchData, setPitchData] = useState<PitcherModeResponse | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    fetchPitcherMode(id)
      .then((payload) => {
        if (isMounted) {
          setPitchData(payload);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setPitchData({
            lead_id: id,
            subject_line: `Error: Unable to generate pitch`,
            email_body: `Failed to fetch target email copy from the backend AI engine.\n\nError details: ${err.message}`,
          });
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [id, company_name]);

  const handleCopy = async () => {
    if (!pitchData) return;
    const textToCopy = `${pitchData.subject_line}\n\n${pitchData.email_body}`;
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Failed to copy summary:', err);
    }
  };

  const containerClasses = inline
    ? 'side-drawer-card rounded-2xl border border-[var(--nexa-accent)]/30 bg-nexa-surface p-5 space-y-4 shadow-sm animate-fade-in my-3'
    : 'pitcher-mode-drawer fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-nexa-border bg-[#0a0a0f]/90 backdrop-blur-2xl p-6 shadow-2xl sm:w-[460px]';

  return (
    <motion.div 
      initial={{ opacity: 0, y: inline ? 10 : 0, x: inline ? 0 : '100%' }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      exit={{ opacity: 0, y: inline ? 10 : 0, x: inline ? 0 : '100%' }}
      className={containerClasses}
    >

      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-nexa-border pb-3">
        <div>
          <h2
            className="text-sm font-bold uppercase tracking-wide"
            style={{ color: 'var(--nexa-accent)' }}
          >
            Intent Summary
          </h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-zinc-400 font-medium">
            Summarised signal context for {company_name}
          </p>
        </div>
        <button
          aria-label="Close Intent Summary"
          className="rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800/80 p-2 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 transition cursor-pointer shrink-0"
          onClick={onClose}
          type="button"
        >
          <X size={15} aria-hidden="true" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto pt-2.5 pb-4">
        {loading ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center font-mono text-xs text-slate-500 dark:text-zinc-600">
            <Loader2
              className="animate-spin text-emerald-500"
              size={22}
              aria-hidden="true"
            />
            Summarizing buyer signals & intent insights...
          </div>
        ) : (
          <div className="space-y-4">
            <label className="block space-y-2">
              <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-zinc-400">
                Summary Title
              </span>
              <input
                className="deep-research-input w-full rounded-xl border border-slate-200 dark:border-nexa-border bg-slate-100 dark:bg-nexa-card p-3 text-xs font-bold text-slate-900 dark:text-zinc-200 outline-none"
                readOnly
                type="text"
                value={pitchData?.subject_line ?? ''}
              />
            </label>
            <label className="block space-y-2 flex-1 flex flex-col">
              <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-zinc-400">
                Intent Signals Summary
              </span>
              <div className="deep-research-box flex-1 min-h-[280px] w-full overflow-y-auto rounded-2xl border border-slate-200 dark:border-nexa-border bg-slate-50 dark:bg-nexa-card p-4 text-sm leading-relaxed text-slate-800 dark:text-zinc-300 outline-none">
                {pitchData?.email_body ? parseMarkdown(pitchData.email_body) : ''}
              </div>
            </label>
          </div>
        )}
      </div>

      {/* Action Button */}
      {!loading && (
        <button
          className={`flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-xs font-bold transition-all shadow-md ${
            copied ? 'text-white' : 'text-nexa-bg hover:brightness-110'
          }`}
          style={{ background: copied ? 'var(--nexa-emerald)' : 'var(--nexa-accent)' }}
          onClick={handleCopy}
          type="button"
        >
          {copied ? (
            <>
              <Check size={16} aria-hidden="true" className="text-white" />
              <span>Copied to Clipboard!</span>
            </>
          ) : (
            <>
              <Clipboard size={16} aria-hidden="true" />
              <span>Copy Summary</span>
            </>
          )}
        </button>
      )}
    </motion.div>
  );
}

