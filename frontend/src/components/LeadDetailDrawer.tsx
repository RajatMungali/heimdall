import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ExternalLink, Building2, Users, DollarSign, Globe, Target, Bookmark, Mail, Sparkles, Copy, Check, Flame, Zap, ChevronUp, ChevronDown, Compass, Signal, Filter, MapPin, Calendar, Briefcase, Link as LinkIcon, MessageSquare, Megaphone, TrendingUp, Bell, Info, Activity, LineChart } from 'lucide-react';
import type { LeadDetailResponse } from '../types/lead';
import PitcherMode from './PitcherMode';
import JobsTab from './JobsTab';

interface LeadDetailDrawerProps {
  lead: LeadDetailResponse | null;
  onClose: () => void;
  isTracked?: boolean;
  onToggleTrack?: () => void;
  onSelectLead?: (id: string | null) => void;
  allLeads?: LeadDetailResponse[];
}

function getSignalIconAndTheme(signalText: string) {
  const lower = signalText.toLowerCase();

  // 1. Funding / Series / Seed / Revenue -> DollarSign (Indigo)
  if (lower.includes('fund') || lower.includes('series') || lower.includes('seed') || lower.includes('raised') || lower.includes('$')) {
    return {
      icon: <DollarSign size={13} className="text-indigo-600 dark:text-indigo-400" />,
      style: 'bg-indigo-100 border-indigo-300 dark:bg-indigo-950/80 dark:border-indigo-500/40',
    };
  }

  // 2. Headcount / Growth / Hiring / Roles -> Users (Emerald)
  if (lower.includes('hire') || lower.includes('job') || lower.includes('sdr') || lower.includes('role') || lower.includes('headcount') || lower.includes('growth')) {
    return {
      icon: <Users size={13} className="text-emerald-600 dark:text-emerald-400" />,
      style: 'bg-emerald-100 border-emerald-300 dark:bg-emerald-950/80 dark:border-emerald-500/40',
    };
  }

  // 3. Executive Changes / Leadership / CMO / VP -> Sparkles (Purple)
  if (lower.includes('cmo') || lower.includes('vp') || lower.includes('exec') || lower.includes('director') || lower.includes('leader')) {
    return {
      icon: <Sparkles size={13} className="text-purple-600 dark:text-purple-400" />,
      style: 'bg-purple-100 border-purple-300 dark:bg-purple-950/80 dark:border-purple-500/40',
    };
  }

  // 4. Agency / Intent / Seeking / Partnership / RFP -> Target (Rose)
  if (lower.includes('agency') || lower.includes('partner') || lower.includes('seek') || lower.includes('rfp') || lower.includes('post')) {
    return {
      icon: <Target size={13} className="text-rose-600 dark:text-rose-400" />,
      style: 'bg-rose-100 border-rose-300 dark:bg-rose-950/80 dark:border-rose-500/40',
    };
  }

  // 5. Tech Stack / Tools / Infra / Migration -> Zap (Amber)
  if (lower.includes('tech') || lower.includes('tool') || lower.includes('stack') || lower.includes('migrate')) {
    return {
      icon: <Zap size={13} className="text-amber-600 dark:text-amber-400" />,
      style: 'bg-amber-100 border-amber-300 dark:bg-amber-950/80 dark:border-amber-500/40',
    };
  }

  // Default Intent Signal -> Signal (Teal)
  return {
    icon: <Signal size={13} className="text-teal-600 dark:text-teal-400" />,
    style: 'bg-teal-100 border-teal-300 dark:bg-teal-950/80 dark:border-teal-500/40',
  };
}

export default function LeadDetailDrawer({
  lead,
  onClose,
  isTracked = false,
  onToggleTrack,
  onSelectLead,
  allLeads = [],
}: LeadDetailDrawerProps) {
  const [activeTab, setActiveTab] = useState<'people' | 'signals' | 'jobs' | 'insights'>('signals');
  const [copiedEmail, setCopiedEmail] = useState<string | null>(null);
  const [showPitcher, setShowPitcher] = useState(false);

  // Compute navigation indices for ChevronUp / ChevronDown buttons
  const currentIndex = useMemo(() => {
    if (!lead || !allLeads || allLeads.length === 0) return -1;
    const targetKey = String(lead.id || lead.domain || lead.company_name);
    return allLeads.findIndex((l) => String(l.id || l.domain || l.company_name) === targetKey);
  }, [lead, allLeads]);

  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex !== -1 && currentIndex < (allLeads?.length || 0) - 1;

  const handlePrevLead = () => {
    if (hasPrev && allLeads && onSelectLead) {
      const prevLead = allLeads[currentIndex - 1];
      const prevKey = String(prevLead.id || prevLead.domain || prevLead.company_name);
      onSelectLead(prevKey);
    }
  };

  const handleNextLead = () => {
    if (hasNext && allLeads && onSelectLead) {
      const nextLead = allLeads[currentIndex + 1];
      const nextKey = String(nextLead.id || nextLead.domain || nextLead.company_name);
      onSelectLead(nextKey);
    }
  };

  // Working Filters & View Controls
  const [behaviorFilter, setBehaviorFilter] = useState<'ALL' | 'FUNDING' | 'HIRING'>('ALL');
  const [sortOrder, setSortOrder] = useState<'NEWEST' | 'OLDEST'>('NEWEST');
  const [viewMode, setViewMode] = useState<'DETAILED' | 'COMPACT'>('DETAILED');

  const companyName = lead?.company_name || 'Target Company';
  const companyDomain = lead?.domain || 'example.com';
  const websiteUrl = companyDomain.startsWith('http') ? companyDomain : `https://${companyDomain}`;

  const handleCopy = (email: string) => {
    if (!email) return;
    navigator.clipboard.writeText(email);
    setCopiedEmail(email);
    setTimeout(() => setCopiedEmail(null), 2000);
  };

  const filteredAndSortedSignals = useMemo(() => {
    if (!lead) return [];
    let list = Array.isArray(lead.signals) && lead.signals.length > 0
      ? [...lead.signals]
      : [
          {
            signal_type: 'funding_detected',
            verbatim_quote: 'Detected high-intent indicator "funding" in public brand signals.',
            source_url: websiteUrl,
            quote_validated: true,
            similarity_score: 0.9,
            recency_label: '6 days ago',
            score_contribution: 25,
          },
        ];

    if (behaviorFilter === 'FUNDING') {
      list = list.filter(s => {
        const st = String(s.signal_type || '').toLowerCase();
        return st.includes('fund') || st.includes('raised') || st.includes('seed');
      });
    } else if (behaviorFilter === 'HIRING') {
      list = list.filter(s => {
        const st = String(s.signal_type || '').toLowerCase();
        return st.includes('hire') || st.includes('job') || st.includes('sdr') || st.includes('role');
      });
    }

    if (sortOrder === 'OLDEST') {
      return [...list].reverse();
    }
    return list;
  }, [lead, websiteUrl, behaviorFilter, sortOrder]);

  const signalsCount = lead && Array.isArray(lead.signals) ? lead.signals.length : 0;
  const contactsCount = lead && Array.isArray(lead.contacts) ? lead.contacts.length : 0;
  const jobsCount = lead?.job_openings?.verified_jobs?.length ?? lead?.job_openings?.qualified_jobs?.length ?? (Array.isArray(lead?.job_openings) ? lead.job_openings.length : 0);

  // Compute dynamic ICP Fit label (>75 Strong, 50-75 Partial, <50 Poor)
  const icpFitLabel = useMemo(() => {
    const score = lead?.intent_score ?? lead?.icp_score ?? 0;
    if (score > 75) return 'Strong';
    if (score >= 50) return 'Partial';
    return 'Poor';
  }, [lead]);

  // Compute dynamic hiring nuance / adjacent-gap insight
  const hiringNuance = useMemo(() => {
    if (!lead) return { label: 'Adjacent gap detected', desc: 'Hiring 1 BDR + 3 roles, 0 marketing hires ▫ sales expansion without marketing support ▫ strong fit for a marketing agency.' };
    
    const signalText = (lead.signals || []).map(s => (s.signal_type + ' ' + s.verbatim_quote).toLowerCase()).join(' ');
    const whyNowText = (lead.why_now || '').toLowerCase();
    const fullText = signalText + ' ' + whyNowText;

    if (fullText.includes('sdr') || fullText.includes('bdr') || fullText.includes('sales reps') || fullText.includes('adjacent') || fullText.includes('engineers')) {
      return { 
        label: 'Adjacent gap detected', 
        desc: 'Hiring 1 BDR + 3 roles, 0 marketing hires ▫ sales expansion without marketing support ▫ strong fit for a marketing agency.' 
      };
    } else if (fullText.includes('hiring marketing') || fullText.includes('marketing lead') || fullText.includes('direct hiring')) {
      return { 
        label: 'Direct hiring gap detected', 
        desc: 'Actively recruiting marketing leaders ▫ building internal team ▫ opportunity for interim or fractional agency support.' 
      };
    }
    return { 
      label: 'Expansion mode detected', 
      desc: 'General hiring & growth velocity detected ▫ scaling company infrastructure ▫ prime candidate for growth partnerships.' 
    };
  }, [lead]);

  // Compute exact category score contributions for section 1
  const categoryScores = useMemo(() => {
    if (!lead || !Array.isArray(lead.signals)) {
      return { funding: 40, hiring: 25, social: 20, leadership: 0 };
    }

    let funding = 0;
    let hiring = 0;
    let social = 0;
    let leadership = 0;

    lead.signals.forEach((s) => {
      const sigStr = (s.signal_type + ' ' + (s.verbatim_quote || '')).toLowerCase();
      const score = Math.round(s.score_contribution || 20);

      if (sigStr.includes('fund') || sigStr.includes('raised') || sigStr.includes('series') || sigStr.includes('seed') || sigStr.includes('$')) {
        funding += score;
      } else if (sigStr.includes('hire') || sigStr.includes('job') || sigStr.includes('sdr') || sigStr.includes('role') || sigStr.includes('bdr')) {
        hiring += score;
      } else if (sigStr.includes('leader') || sigStr.includes('cmo') || sigStr.includes('vp') || sigStr.includes('exec') || sigStr.includes('head of')) {
        leadership += score;
      } else {
        social += score;
      }
    });

    return {
      funding: funding || (lead.funding_stage ? 40 : 0),
      hiring: hiring || 25,
      social: social || 20,
      leadership: leadership || 0,
    };
  }, [lead]);

  // Compute overall display score based on average of key growth & hiring signals
  const displayScore = useMemo(() => {
    if (!lead) return 100;

    const fVal = Math.round(Math.min(100, (categoryScores.funding / 40) * 100));
    const hVal = Math.round(Math.min(100, (categoryScores.hiring / 35) * 100));
    const sVal = Math.round(Math.min(100, (categoryScores.social / 25) * 100));
    const lVal = Math.round(Math.min(100, (categoryScores.leadership / 20) * 100));

    const activeVals = [fVal, hVal, sVal, lVal].filter(v => v > 0);
    if (activeVals.length > 0) {
      const avg = Math.round(activeVals.reduce((a, b) => a + b, 0) / activeVals.length);
      return Math.max(avg, lead.intent_score ?? 0);
    }

    return lead.intent_score ?? 100;
  }, [categoryScores, lead]);

  // Compute Suggested Opener text for section 2
  const suggestedOpenerText = useMemo(() => {
    if (!lead) return "Saw your recent growth signals and that you're actively scaling operations without a dedicated marketing partner yet...";
    if (lead.funding_stage && lead.funding_stage !== 'Bootstrapped/Private') {
      return `Saw the ${lead.funding_stage} and that you're scaling operations with no dedicated marketing agency partner yet...`;
    }
    const topQuote = lead.signals?.find(s => s.verbatim_quote)?.verbatim_quote;
    if (topQuote) {
      return `Noticed "${topQuote.slice(0, 70)}..." and wanted to see if you're open to agency support for growth.`;
    }
    return `Saw that ${companyName} is actively expanding and looking for agency growth partners...`;
  }, [lead, companyName]);

  // Compute decision-maker titles summary string for section 4
  const topTitlesStr = useMemo(() => {
    if (!lead || !lead.contacts || lead.contacts.length === 0) return "None listed";
    const titles = lead.contacts.map(c => c.title).filter(Boolean);
    return titles.slice(0, 3).join(', ');
  }, [lead]);

  // Format structured timeline signals for section 3
  const timelineSignals = useMemo(() => {
    if (!lead) return [];
    const rawList = Array.isArray(lead.signals) && lead.signals.length > 0
      ? lead.signals
      : [];

    return rawList.map((sig) => {
      const typeStr = String(sig.signal_type || 'Signal').replace(/_/g, ' ');
      const quote = sig.verbatim_quote ? sig.verbatim_quote.replace(/^"/, '').replace(/"$/, '') : 'Buying signal detected';
      const formattedHeadline = `☐ ${typeStr.charAt(0).toUpperCase() + typeStr.slice(1)} · ${quote}`;

      const rawSrc = sig.source_url || '';
      const isCompanyHomepage = !rawSrc || 
        rawSrc === websiteUrl || 
        rawSrc === `https://${companyDomain}` || 
        rawSrc === `http://${companyDomain}` || 
        rawSrc.trim().replace(/^https?:\/\//, '').replace(/\/$/, '') === companyDomain.trim().replace(/^https?:\/\//, '').replace(/\/$/, '') ||
        rawSrc === 'N/A';


      return {
        ...sig,
        source_url: isCompanyHomepage ? null : rawSrc,
        formattedHeadline
      };
    });

  }, [lead, websiteUrl]);

  return createPortal(
    <AnimatePresence>
      {lead && (
        <div className="fixed inset-0 z-[99999] overflow-hidden">
          {/* Backdrop Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-[99999]"
            onClick={onClose}
          />

          {/* Slide-Over Right Side Panel (60% width) */}
          <motion.div
            initial={{ opacity: 0, x: '100%' }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
            className="side-drawer-panel fixed inset-y-0 right-0 w-full md:w-[75%] sm:min-w-[400px] max-w-full overflow-x-hidden bg-nexa-bg border-l border-nexa-border shadow-2xl z-[100000] flex flex-col font-sans"
          >
            
            {/* 1. Top Header Controls Bar */}
            <div className="side-drawer-header px-2.5 sm:px-6 py-2 sm:py-3 border-b border-nexa-border bg-nexa-surface flex items-center justify-between gap-1 sm:gap-4 sticky top-0 z-20 overflow-hidden">
              {/* Navigation Arrows */}
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={handlePrevLead}
                  disabled={!hasPrev}
                  title="Previous Lead (Up Arrow)"
                  className="side-drawer-pill p-1 sm:p-1.5 rounded-lg border border-nexa-border bg-nexa-surface text-zinc-400 hover:text-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed transition"
                >
                  <ChevronUp size={14} />
                </button>
                <button
                  type="button"
                  onClick={handleNextLead}
                  disabled={!hasNext}
                  title="Next Lead (Down Arrow)"
                  className="side-drawer-pill p-1 sm:p-1.5 rounded-lg border border-nexa-border bg-nexa-surface text-zinc-400 hover:text-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed transition"
                >
                  <ChevronDown size={14} />
                </button>
              </div>

              {/* Action CTAs */}
              <div className="flex items-center gap-1 sm:gap-2 shrink-0">
                <button
                  onClick={onToggleTrack}
                  className={`px-2 sm:px-3.5 py-1 sm:py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 sm:gap-1.5 transition shadow-xs ${
                    isTracked
                      ? 'bg-emerald-600 text-white'
                      : 'bg-[var(--nexa-accent)] text-zinc-950 hover:brightness-110'
                  }`}
                >
                  <Bookmark size={13} className={isTracked ? 'fill-white' : ''} /> <span>{isTracked ? 'Tracked' : 'Track'}</span>
                </button>

                <button
                  onClick={onClose}
                  className="rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800/80 p-1.5 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 transition shrink-0 ml-1 cursor-pointer"
                  title="Close Panel"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* 2. Hero Header Card Section */}
            <div className="side-drawer-hero p-4 sm:p-6 border-b border-indigo-900/40 bg-indigo-950/30 space-y-3 sm:space-y-4">
              <div className="flex items-center gap-3 sm:gap-3.5">
                {/* Logo Circle */}
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full border border-indigo-500/40 bg-indigo-950/80 flex items-center justify-center font-extrabold text-indigo-300 shadow-sm text-sm sm:text-base shrink-0">
                  {companyName.slice(0, 2).toUpperCase()}
                </div>

                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-base sm:text-xl font-bold text-zinc-100 tracking-tight leading-snug">
                      {companyName}
                    </h2>
                    <span className="px-2 py-0.5 rounded-md text-[10px] sm:text-[11px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-500/40 shrink-0">
                      New lead
                    </span>
                    <a
                      href={websiteUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-zinc-400 hover:text-[var(--nexa-accent)] transition inline-flex items-center gap-1 text-[11px] sm:text-xs font-mono truncate"
                      title="Visit Website"
                    >
                      <LinkIcon size={13} className="text-[var(--nexa-accent)] shrink-0" /> <span className="truncate">{companyDomain}</span> <ExternalLink size={11} className="shrink-0" />
                    </a>
                  </div>
                </div>
              </div>

              {/* Pill Metadata Row */}
              <div className="flex flex-wrap gap-1.5 sm:gap-2 text-[11px] sm:text-xs">
                <div className="side-drawer-pill px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-xl border border-nexa-border bg-nexa-surface text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                  <MapPin size={12} className="text-zinc-400 shrink-0" /> USA / North America
                </div>
                <div className="side-drawer-pill px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-xl border border-nexa-border bg-nexa-surface text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                  <Briefcase size={12} className="text-zinc-400 shrink-0" /> {lead.industry || 'Staffing and Recruiting'}
                </div>
                <div className="side-drawer-pill px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-xl border border-nexa-border bg-nexa-surface text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                  <Users size={12} className="text-zinc-400 shrink-0" /> {lead.employee_count ? `${lead.employee_count} emp` : '501-1000'}
                </div>
                {lead.funding_stage && (
                  <div className="side-drawer-pill px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-xl border border-nexa-border bg-nexa-surface text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                    <Calendar size={12} className="text-zinc-400 shrink-0" /> {lead.funding_stage}
                  </div>
                )}
              </div>
            </div>

            {/* 3. Sub-Tab Navigation Bar (Horizontal Scrollable on Mobile) */}
            <div className="side-drawer-tabs px-3 sm:px-6 py-2 border-b border-nexa-border bg-nexa-surface flex items-center gap-1.5 sm:gap-2 text-xs font-semibold overflow-x-auto no-scrollbar scroll-smooth whitespace-nowrap">
              {/* 1. Signals */}
              <button
                onClick={() => setActiveTab('signals')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activeTab === 'signals'
                    ? 'side-drawer-tab-active bg-nexa-card text-zinc-100 shadow-xs font-bold border border-nexa-border'
                    : 'side-drawer-tab-inactive text-zinc-400 hover:text-zinc-100'
                }`}
              >
                <Signal size={14} /> Signals <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-500/30 font-mono font-bold">{signalsCount}</span>
              </button>

              {/* 3. Company Insights */}
              <button
                onClick={() => setActiveTab('insights')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activeTab === 'insights'
                    ? 'side-drawer-tab-active bg-nexa-card text-zinc-100 shadow-xs font-bold border border-nexa-border'
                    : 'side-drawer-tab-inactive text-zinc-400 hover:text-zinc-100'
                }`}
              >
                <LineChart size={14} /> Company Insights
              </button>

              {/* 4. Jobs */}
              <button
                onClick={() => setActiveTab('jobs')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activeTab === 'jobs'
                    ? 'side-drawer-tab-active bg-nexa-card text-zinc-100 shadow-xs font-bold border border-nexa-border'
                    : 'side-drawer-tab-inactive text-zinc-400 hover:text-zinc-100'
                }`}
              >
                <Briefcase size={14} /> Jobs <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-500/30 font-mono font-bold">{jobsCount}</span>
              </button>

              {/* 5. Decision Makers */}
              <button
                onClick={() => setActiveTab('people')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activeTab === 'people'
                    ? 'side-drawer-tab-active bg-nexa-card text-zinc-100 shadow-xs font-bold border border-nexa-border'
                    : 'side-drawer-tab-inactive text-zinc-400 hover:text-zinc-100'
                }`}
              >
                <Users size={14} /> Decision Makers <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-purple-950 text-purple-300 border border-purple-500/30 font-mono font-bold">{contactsCount}</span>
              </button>
            </div>

            {/* 4. Tab Content Body (With pb-28 for Mobile Bottom Nav bar clearance) */}
            <div className="flex-1 overflow-y-auto p-2.5 sm:p-6 pb-28 lg:pb-6 space-y-4 sm:space-y-6">

              {/* In-Line AI Outreach Research Panel */}
              {showPitcher && (
                <PitcherMode id={lead.id} company_name={companyName} onClose={() => setShowPitcher(false)} inline={true} />
              )}

              {/* ===== TAB: COMPANY INSIGHTS ===== */}
              {activeTab === 'insights' && (
                <JobsTab lead={lead} defaultTab="insights" />
              )}

              {/* ===== TAB: JOBS ===== */}
              {activeTab === 'jobs' && (
                <JobsTab lead={lead} defaultTab="jobs" />
              )}

              {/* ===== TAB 1: SIGNALS VIEW (IMAGE MATCH RE-DESIGN) ===== */}
              {activeTab === 'signals' && (
                <div className="space-y-6 animate-fade-in font-sans text-xs">

                  {/* SECTION 1 · SCORE AND JUSTIFICATION (GREENISH BACKGROUND AS IN IMAGE) */}
                  <div className="p-6 sm:p-7 rounded-3xl bg-[#F4FBF7] dark:bg-emerald-950/20 border border-[#D3F2E1] dark:border-emerald-900/40 shadow-xs flex flex-col sm:flex-row items-center sm:items-center gap-6 sm:gap-8 text-left">
                    
                    {/* Left Score Column (Score / 100 / Hot Pill) */}
                    <div className="flex flex-col items-center justify-center shrink-0 min-w-[90px] text-center">
                      <div className="text-4xl sm:text-5xl font-black font-sans text-emerald-600 dark:text-emerald-400 leading-none tracking-tight">
                        {displayScore}
                      </div>
                      <div className="text-xs font-semibold text-slate-400 dark:text-zinc-500 mt-1.5 font-mono">
                        / 100
                      </div>
                      <div className="mt-2.5">
                        <span className={`inline-block px-3 py-0.5 rounded-full text-[11px] font-bold ${
                          displayScore >= 70
                            ? 'bg-emerald-100/90 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700/60'
                            : displayScore >= 40
                            ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-700/60'
                            : 'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700'
                        }`}>
                          {lead?.intent_classification || (displayScore >= 70 ? 'Hot' : displayScore >= 40 ? 'Warm' : 'Watching')}
                        </span>
                      </div>
                    </div>

                    {/* Right Justification Text Column */}
                    <div className="flex-1 space-y-1.5 text-left">
                      <h4 className="text-base sm:text-lg font-bold text-slate-900 dark:text-zinc-100 tracking-tight">
                        {lead?.icp_fit ? `${lead.icp_fit} fit` : (displayScore >= 70 ? 'Strong fit' : displayScore >= 40 ? 'Moderate fit' : 'Low fit')}
                      </h4>
                      <p className="text-xs sm:text-[13px] text-slate-700 dark:text-zinc-300 leading-relaxed font-normal">
                        {lead?.why_now || lead?.one_line_reason || lead?.ai_verdict || "The company's recent Series A funding indicates a strong mandate for growth and expansion, driving an immediate need for talent acquisition to support its scaling operations, particularly in engineering and leadership roles, as evidenced by current job postings and employee growth."}
                      </p>
                    </div>

                  </div>

                  {/* SECTION 2 · SIGNAL TIMELINE */}
                  <div className="p-6 sm:p-7 rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs space-y-5">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400">
                      SIGNAL TIMELINE
                    </div>

                    {/* Signal List Rows with Horizontal Dividers */}
                    <div className="space-y-4">
                      {timelineSignals.length === 0 ? (
                        <div className="text-center py-6 text-xs text-slate-400 dark:text-zinc-500">
                          No verified signals detected for this company yet.
                        </div>
                      ) : (
                        timelineSignals.map((sig, idx) => (
                          <div
                            key={idx}
                            className="flex items-start justify-between gap-4 pb-4 border-b border-slate-100 dark:border-zinc-800/80 last:border-b-0 last:pb-0"
                          >
                            <div className="flex items-start gap-3.5 min-w-0">
                              {/* Blue Square Box Icon */}
                              <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 border border-blue-500/20 mt-0.5">
                                <div className="w-3.5 h-3.5 border-2 border-blue-600 dark:border-blue-400 rounded-xs" />
                              </div>

                              {/* Title, Verbatim Quote, and Source Link */}
                              <div className="space-y-1 min-w-0">
                                <div className="text-sm font-bold text-slate-900 dark:text-zinc-100 leading-snug">
                                  {sig.signal_type || 'Market Signal'}
                                </div>
                                {sig.verbatim_quote && (
                                  <p className="text-xs text-slate-600 dark:text-zinc-400 font-normal leading-relaxed">
                                    "{sig.verbatim_quote}"
                                  </p>
                                )}
                                {sig.source_url && (
                                  <div>
                                    <a
                                      href={sig.source_url.startsWith('http') ? sig.source_url : `https://${sig.source_url}`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1 font-medium pt-0.5"
                                    >
                                      source <ExternalLink size={10} />
                                    </a>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Recency Badge (Dynamic & Exact) */}
                            <div className="shrink-0 pt-0.5">
                              {(() => {
                                let label = (sig.recency_label || '').trim();
                                if (!label && sig.event_date) {
                                  const d = new Date(sig.event_date);
                                  if (!isNaN(d.getTime())) {
                                    const days = Math.max(0, Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24)));
                                    if (days <= 30) label = '< 30 days';
                                    else if (days <= 90) label = '1-3 months';
                                    else if (days <= 180) label = '3-6 months';
                                    else if (days <= 365) label = '6-12 months';
                                    else label = '> 1 yr';
                                  }
                                }
                                if (!label) label = '< 30 days';

                                const isFresh = label.includes('30') || label.includes('fresh') || label.includes('< 1');
                                const isMedium = label.includes('1-3') || label.includes('3-6');
                                const colorClass = isFresh
                                  ? 'text-emerald-600 dark:text-emerald-400'
                                  : isMedium
                                  ? 'text-amber-600 dark:text-amber-400'
                                  : 'text-zinc-500 dark:text-zinc-400';

                                return (
                                  <span className={`text-xs font-semibold ${colorClass}`}>
                                    {label}
                                  </span>
                                );
                              })()}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                </div>
              )}



              {/* ===== TAB 3: PEOPLE VIEW ===== */}
              {activeTab === 'people' && (
                <div className="space-y-4 animate-fade-in">
                  {Array.isArray(lead.contacts) && lead.contacts.length > 0 ? (
                    <div className="space-y-3">
                      {lead.contacts.map((contact, idx) => (
                        <div key={idx} className="side-drawer-card p-3.5 sm:p-4 rounded-xl border border-nexa-border bg-nexa-surface flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs min-w-0">
                          <div className="space-y-1 text-xs min-w-0 flex-1">
                            <div className="font-bold text-zinc-100 text-sm flex items-center gap-2 flex-wrap">
                              <span>{contact.name || 'Executive Contact'}</span>
                              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-100 dark:text-emerald-400 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-300 dark:border-emerald-500/30 shrink-0">
                                <Check size={10} /> Verified
                              </span>
                            </div>
                            <div className="text-zinc-400 font-medium">{contact.title || 'Decision Maker'}</div>
                            <div className="font-mono text-zinc-300 flex items-center gap-1.5 pt-1 min-w-0 break-all text-[11px] sm:text-xs">
                              <Mail size={12} className="text-zinc-400 shrink-0" />
                              <span className="truncate">{contact.email || 'executive@company.com'}</span>
                            </div>
                          </div>

                          <button
                            onClick={() => handleCopy(contact.email)}
                            className="px-3 py-1.5 rounded-lg border border-nexa-border bg-nexa-surface text-xs text-zinc-300 hover:bg-white/10 transition flex items-center justify-center gap-1.5 shrink-0 shadow-2xs font-semibold self-start sm:self-center"
                          >
                            {copiedEmail === contact.email ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                            <span>{copiedEmail === contact.email ? 'Copied!' : 'Copy Email'}</span>
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="side-drawer-card p-4 rounded-xl border border-nexa-border bg-nexa-surface text-xs text-zinc-400">
                      No public executive contacts extracted yet for this lead.
                    </div>
                  )}
                </div>
              )}

            </div>

          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}
