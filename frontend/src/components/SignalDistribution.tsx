import { useMemo } from 'react';
import type { LeadDetailResponse } from '../types/lead';

interface SignalDistributionProps {
  leads: LeadDetailResponse[];
}

const SIGNAL_LABELS: Record<string, string> = {
  sdr_hiring: 'SDR Hiring',
  funding_round: 'Funding Round',
  growth_news: 'Growth News',
  upmarket_pivot: 'Upmarket Pivot',
};

// Generate a mini sparkline waveform pattern for visual interest
function MiniWaveform({ seed, color }: { seed: number; color: string }) {
  const points: number[] = [];
  // Deterministic pseudo-random waveform based on seed
  let val = seed * 17;
  for (let i = 0; i < 20; i++) {
    val = ((val * 1103515245 + 12345) & 0x7fffffff) % 100;
    points.push(val);
  }

  const maxVal = Math.max(...points, 1);
  const svgWidth = 100;
  const svgHeight = 24;
  const step = svgWidth / (points.length - 1);
  const polyline = points
    .map((v, i) => `${i * step},${svgHeight - (v / maxVal) * (svgHeight - 4)}`)
    .join(' ');

  return (
    <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-5 w-20" preserveAspectRatio="none">
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}

export default function SignalDistribution({ leads }: SignalDistributionProps) {
  const stats = useMemo(() => {
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
      .sort((a, b) => b.count - a.count);
  }, [leads]);

  return (
    <div className="nexa-card w-full p-5 flex-shrink-0">
      <h3 className="mb-4 text-sm font-semibold text-zinc-100">Signal Type Trends</h3>
      {stats.length === 0 ? (
        <p className="py-6 text-center font-mono text-xs text-zinc-600">
          No signal data yet…
        </p>
      ) : (
        <div className="space-y-4">
          {stats.map((stat, idx) => (
            <div key={stat.type} className="flex items-center justify-between gap-3">
              <span className="w-28 truncate text-sm text-zinc-400">
                {SIGNAL_LABELS[stat.type] || stat.type}
              </span>
              <MiniWaveform
                seed={idx + 1}
                color={idx === 0 ? 'var(--nexa-accent)' : 'var(--nexa-text-muted)'}
              />
              <span className="w-12 text-right font-mono text-sm font-semibold text-zinc-300">
                {stat.percentage} %
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
