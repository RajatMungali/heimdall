import { useMemo } from 'react';
import { CircleAlert } from 'lucide-react';
import type { LeadDetailResponse } from '../types/lead';

interface SignalAnalyticsProps {
  leads: LeadDetailResponse[];
}

interface SignalStat {
  type: string;
  count: number;
  percentage: number;
}

const SIGNAL_LABELS: Record<string, string> = {
  sdr_hiring: 'SDR Hiring Spikes',
  funding_round: 'Funding News',
  growth_news: 'Growth Expansion',
  upmarket_pivot: 'Upmarket Pivot',
};

export default function SignalAnalytics({ leads }: SignalAnalyticsProps) {
  const stats = useMemo<SignalStat[]>(() => {
    const allSignals = leads.flatMap((l) => l.signals);
    if (allSignals.length === 0) return [];

    const counts: Record<string, number> = {};
    for (const signal of allSignals) {
      const key = signal.signal_type;
      counts[key] = (counts[key] || 0) + 1;
    }

    const total = allSignals.length;
    return Object.entries(counts)
      .map(([type, count]) => ({
        type,
        count,
        percentage: Math.round((count / total) * 100),
      }))
      .sort((a, b) => b.percentage - a.percentage)
      .slice(0, 4);
  }, [leads]);

  return (
    <div className="nexa-card p-5 flex-shrink-0">
      <h3 className="mb-4 text-sm font-semibold text-zinc-100">
        Top Signal Origins
      </h3>
      {stats.length === 0 ? (
        <p className="py-6 text-center font-mono text-xs text-zinc-600">
          Awaiting signal ingestion…
        </p>
      ) : (
        <div className="space-y-4">
          {stats.map((stat, idx) => (
            <div key={stat.type} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <span
                  className="flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold"
                  style={{
                    background: idx === 0 ? 'var(--nexa-accent-dim)' : 'var(--nexa-surface)',
                    color: idx === 0 ? 'var(--nexa-accent)' : 'var(--nexa-text-muted)',
                  }}
                >
                  {idx + 1}
                </span>
                <span className="text-sm text-zinc-300">
                  {SIGNAL_LABELS[stat.type] || stat.type}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <CircleAlert
                  size={14}
                  className="text-zinc-600"
                  aria-hidden="true"
                />
                <span
                  className="font-mono text-sm font-semibold"
                  style={{
                    color: idx === 0 ? 'var(--nexa-accent)' : 'var(--nexa-text-secondary)',
                  }}
                >
                  {stat.percentage}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
