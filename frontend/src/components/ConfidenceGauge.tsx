import { useMemo, useState, useEffect } from 'react';

interface ConfidenceGaugeProps {
  verified: number;
  total: number;
  noCard?: boolean;
}

export default function ConfidenceGauge({ verified, total, noCard }: ConfidenceGaugeProps) {
  const targetPercentage = useMemo(() => {
    if (total === 0) return 0;
    return Math.round((verified / total) * 100);
  }, [verified, total]);

  const [percentage, setPercentage] = useState(0);

  // Trigger animation on mount
  useEffect(() => {
    const timer = setTimeout(() => setPercentage(targetPercentage), 50);
    return () => clearTimeout(timer);
  }, [targetPercentage]);

  // SVG semi-circular arc geometry
  const cx = 120;
  const cy = 110;
  const r = 85;
  const startAngle = 180; // left
  const endAngle = 0;     // right (semi-circle)
  const circumference = Math.PI * r;
  const filledLength = (percentage / 100) * circumference;
  const dashOffset = circumference - filledLength;

  // Convert angle to SVG arc coordinates
  const polarToCartesian = (angle: number, radius: number) => {
    const rad = (angle * Math.PI) / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy - radius * Math.sin(rad),
    };
  };

  const start = polarToCartesian(startAngle, r);
  const end = polarToCartesian(endAngle, r);
  const arcPath = `M ${start.x} ${start.y} A ${r} ${r} 0 0 1 ${end.x} ${end.y}`;

  // Inner tick marks path
  const innerR = 65;
  const innerStart = polarToCartesian(startAngle, innerR);
  const innerEnd = polarToCartesian(endAngle, innerR);
  const innerArcPath = `M ${innerStart.x} ${innerStart.y} A ${innerR} ${innerR} 0 0 1 ${innerEnd.x} ${innerEnd.y}`;

  const gaugeColor = 'var(--nexa-accent)';
  const glowColor = 'var(--nexa-accent-glow)';
  const rotation = (percentage / 100) * 180;

  const content = (
    <>
      {/* Background ambient glow matching the image */}
      <div 
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 rounded-full blur-[50px] pointer-events-none"
        style={{ background: 'var(--nexa-accent)', opacity: 0.15 }}
      />
      
      <svg viewBox="0 0 240 140" className="w-full max-w-[260px] relative z-10">
        {/* Inner ticks */}
        <path
          d={innerArcPath}
          fill="none"
          stroke="var(--nexa-border-strong)"
          strokeWidth="2"
          strokeDasharray="1 8"
          strokeLinecap="round"
        />

        {/* Track */}
        <path
          d={arcPath}
          fill="none"
          stroke="var(--nexa-border-strong)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        
        {/* Filled arc */}
        <path
          d={arcPath}
          fill="none"
          stroke={gaugeColor}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{
            transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)',
            filter: `drop-shadow(0 0 6px ${glowColor})`,
          }}
        />

        {/* Glowing Knob/Dot */}
        <g style={{
          transformOrigin: `${cx}px ${cy}px`,
          transform: `rotate(${rotation}deg)`,
          transition: 'transform 1.2s cubic-bezier(0.4, 0, 0.2, 1)'
        }}>
          <circle 
            cx={start.x} 
            cy={start.y} 
            r="6" 
            fill="var(--nexa-bg)" 
            stroke={gaugeColor} 
            strokeWidth="3"
            style={{ filter: `drop-shadow(0 0 8px ${gaugeColor})` }}
          />
        </g>

        {/* Center percentage text */}
        <text
          x={cx}
          y={cy - 10}
          fill="var(--nexa-text-primary)"
          fontFamily="Inter, sans-serif"
          fontWeight="800"
          fontSize="36"
          textAnchor="middle"
        >
          {targetPercentage}%
        </text>
        <text 
          x={cx} 
          y={cy + 15} 
          fill="var(--nexa-text-muted)"
          fontFamily="Inter, sans-serif"
          fontWeight="500"
          fontSize="11"
          textAnchor="middle"
        >
          Contact Reliability
        </text>

      </svg>
    </>
  );

  if (noCard) {
    return (
      <div className="relative flex flex-col items-center justify-center overflow-hidden w-full h-full">
        {content}
      </div>
    );
  }

  return (
    <div className="nexa-card flex flex-col items-center px-5 py-6 relative overflow-hidden flex-shrink-0">
      {content}
    </div>
  );
}
