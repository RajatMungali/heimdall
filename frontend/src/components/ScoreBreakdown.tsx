import { Check, CircleAlert, ExternalLink } from 'lucide-react';
import type { DNSAuditObjective, ExtractedSignal } from '../types/lead';

interface ScoreBreakdownProps {
  signals: ExtractedSignal[];
  dns_audit: DNSAuditObjective;
}

function dnsTone(value: string) {
  if (value === 'Valid') return { color: 'var(--nexa-emerald)', bg: 'var(--nexa-emerald-dim)' };
  if (value.includes('Weak')) return { color: 'var(--nexa-amber)', bg: 'var(--nexa-amber-dim)' };
  return { color: 'var(--nexa-rose)', bg: 'var(--nexa-rose-dim)' };
}

export default function ScoreBreakdown({ signals }: ScoreBreakdownProps) {
  return (
    <section className="animate-fade-in space-y-4 border-t border-nexa-border bg-nexa-bg p-5">
      {/* Evidence Log Panel - Full Width */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-zinc-400">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: 'var(--nexa-accent)' }}
          />
          Extraction Evidence Log
        </h3>
        {signals.length === 0 ? (
          <p className="py-8 text-center font-mono text-sm text-zinc-500">
            No signal evidence captured for this target.
          </p>
        ) : (
          <div className="space-y-3">
            {signals.map((signal) => (
              <article
                key={`${signal.signal_type}-${signal.verbatim_quote}`}
                className="nexa-card p-4 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span
                    className="rounded border px-2.5 py-1 font-mono text-xs font-semibold uppercase tracking-wider"
                    style={{
                      borderColor: 'var(--nexa-accent)',
                      background: 'var(--nexa-accent-dim)',
                      color: 'var(--nexa-accent)',
                    }}
                  >
                    {signal.signal_type.replace(/_/g, ' ')}
                  </span>
                  <span
                    className={`flex items-center gap-1.5 font-mono text-xs font-semibold ${
                      signal.quote_validated ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                  >
                    {signal.quote_validated ? (
                      <Check size={14} aria-hidden="true" />
                    ) : (
                      <CircleAlert size={14} aria-hidden="true" />
                    )}
                    {signal.quote_validated ? 'Verified' : 'Needs Review'} ({signal.similarity_score}%)
                  </span>
                </div>

                <blockquote className="border-l-3 border-[var(--nexa-accent)] py-1.5 pl-4 text-sm font-medium italic leading-6 text-zinc-200 bg-white/5 rounded-r">
                  "{signal.verbatim_quote}"
                </blockquote>

                <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-400 pt-1">
                  <span className="flex items-center gap-4">
                    <span>
                      Recency: <span className="font-semibold uppercase text-zinc-200">{signal.recency_label}</span>
                    </span>
                    {(() => {
                      const url = signal.source_url || '';
                      const isRealArticle = url && 
                        url !== 'N/A' && 
                        url !== 'None' && 
                        !url.endsWith('//') &&
                        url.includes('/');
                      if (!isRealArticle) return null;
                      return (
                        <a
                          href={url.startsWith('http') ? url : `https://${url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 font-medium text-[var(--nexa-accent)] transition-colors hover:underline"
                          title="View source article"
                        >
                          <ExternalLink size={13} />
                          Source Link
                        </a>
                      );
                    })()}

                  </span>
                  <span className="font-mono text-xs">
                    Impact: <span className="font-bold text-emerald-400">+{signal.score_contribution} pts</span>
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

