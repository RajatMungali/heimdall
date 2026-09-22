import { CheckCircle2, CircleAlert } from 'lucide-react';
import type { ConfidenceEvaluation } from '../types/lead';

interface ConfidenceMeterProps {
  confidence: ConfidenceEvaluation;
}

export default function ConfidenceMeter({ confidence }: ConfidenceMeterProps) {
  const isHighTrust = confidence.color === 'emerald';
  const percentage = confidence.total > 0
    ? Math.round((confidence.verified / confidence.total) * 100)
    : 0;

  return (
    <section className="nexa-card flex items-center justify-between px-3.5 py-1.5 min-w-[220px] sm:min-w-[240px]">
      <div className="space-y-0.5">
        <span className="block text-[10px] font-bold uppercase tracking-wider text-zinc-400">
          Contact Reliability
        </span>
        <div className="flex items-center gap-1.5">
          {isHighTrust ? (
            <CheckCircle2 className="text-emerald-400" size={14} aria-hidden="true" />
          ) : (
            <CircleAlert size={14} aria-hidden="true" style={{ color: 'var(--nexa-accent)' }} />
          )}
          <span className="text-xs font-bold text-zinc-100">{confidence.label}</span>
        </div>
      </div>
      <div className="text-right">
        <div className="flex items-baseline justify-end gap-1">
          <span
            className="font-mono text-xl font-bold"
            style={{
              color: isHighTrust ? 'var(--nexa-emerald)' : 'var(--nexa-accent)',
            }}
          >
            {percentage}%
          </span>
        </div>
        <span className="font-mono text-[10px] font-medium text-zinc-400">
          Composite score
        </span>
      </div>
    </section>
  );
}


