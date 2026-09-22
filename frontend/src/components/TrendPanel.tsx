import { useEffect, useState } from 'react';
import { fetchPipelineStatus, type PipelineStatusResponse } from '../lib/api';
import type { LeadDetailResponse } from '../types/lead';

interface TrendPanelProps {
  leads: LeadDetailResponse[];
}

export default function TrendPanel({ leads }: TrendPanelProps) {
  const [telemetry, setTelemetry] = useState<PipelineStatusResponse | null>(null);

  useEffect(() => {
    fetchPipelineStatus().then(setTelemetry).catch(console.error);
  }, []);

  // Generate a sparkline from lead intent scores (or mock bars if no leads)
  const barData = leads.length > 0
    ? leads.map((l) => l.intent_score)
    : [12, 28, 18, 42, 35, 22, 50, 38, 45, 30, 25, 55, 40, 32, 48];

  const maxVal = Math.max(...barData, 1);

  // Build SVG polyline points for the sparkline
  const svgWidth = 600;
  const svgHeight = 100;
  const step = svgWidth / Math.max(barData.length - 1, 1);
  const points = barData
    .map((val, i) => `${i * step},${svgHeight - (val / maxVal) * (svgHeight - 10)}`)
    .join(' ');

  return (
    <div className="nexa-card flex-1 overflow-hidden p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-100">Ingestion Volume Trend</h3>
        <span className="rounded-md border border-nexa-border bg-nexa-surface px-2.5 py-1 font-mono text-xs text-zinc-400">
          {telemetry?.status || 'Idle'}
        </span>
      </div>
      <div className="relative h-[110px] w-full">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="h-full w-full"
          preserveAspectRatio="none"
        >
          {/* Gradient fill below the line */}
          <defs>
            <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--nexa-accent)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--nexa-accent)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {/* Area fill */}
          <polygon
            points={`0,${svgHeight} ${points} ${svgWidth},${svgHeight}`}
            fill="url(#sparkGrad)"
          />
          {/* Line */}
          <polyline
            points={points}
            fill="none"
            stroke="var(--nexa-accent)"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <div className="mt-3 flex items-center gap-4 font-mono text-xs text-zinc-500">
        <span>
          Processed:{' '}
          <span className="font-semibold text-zinc-300">
            {telemetry?.lead_count_processed ?? leads.length}
          </span>
        </span>
        {telemetry?.last_run_time && !isNaN(new Date(telemetry.last_run_time).getTime()) && (
          <span>
            Last run:{' '}
            <span className="text-zinc-400">
              {new Date(telemetry.last_run_time).toLocaleString()}
            </span>
          </span>
        )}
      </div>
    </div>
  );
}
