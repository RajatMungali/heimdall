import { ChevronDown, Sparkles, Trash2, Loader2, Search, Filter, Check, X, SlidersHorizontal, Workflow, Bookmark, Podcast } from 'lucide-react';
import { Fragment, useMemo, useState, useRef, useEffect } from 'react';
import type { LeadDetailResponse, LeadTier } from '../types/lead';
import ConfidenceMeter from './ConfidenceMeter';
import PitcherMode from './PitcherMode';
import ScoreBreakdown from './ScoreBreakdown';
import HackerScanAnimation from './HackerScanAnimation';
import LeadDetailDrawer from './LeadDetailDrawer';
import DocumentMagnifierScan from './DocumentMagnifierScan';
import { ingestLead, deleteLead, runPipeline, fetchLeads } from '../lib/api';

interface LeadTableProps {
  leads: LeadDetailResponse[];
  scannedLeads?: LeadDetailResponse[];
  setScannedLeads?: (leads: LeadDetailResponse[]) => void;
  selectedLeadId: string | null;
  onSelectLead: (id: string | null) => void;
  onLeadIngested?: (newLead: LeadDetailResponse) => void;
  onLeadDeleted?: (id: string) => void;
  status?: 'loading' | 'success' | 'error';
  externalSearchTerm?: string;
  isPipelineTab?: boolean;
  isTrackRecordsTab?: boolean;
  trackedLeadIds?: string[];
  onToggleTrackLead?: (id: string) => void;
}

const tierOptions: Array<LeadTier | 'ALL'> = ['ALL', 'High', 'Medium', 'Low'];

function tierClass(tier: LeadTier) {
  if (tier === 'High')
    return 'border-emerald-500/20 bg-[var(--nexa-emerald-dim)] text-emerald-300';
  if (tier === 'Medium')
    return 'border-amber-500/20 bg-[var(--nexa-amber-dim)] text-amber-300';
  return 'border-nexa-border bg-nexa-surface text-zinc-500';
}

function icpClass(icp_fit: LeadDetailResponse['icp_fit']) {
  if (icp_fit === 'Strong') return 'bg-[var(--nexa-emerald-dim)] text-emerald-300 border-emerald-500/20';
  if (icp_fit === 'Partial') return 'bg-[var(--nexa-amber-dim)] text-amber-300 border-amber-500/20';
  return 'bg-[var(--nexa-rose-dim)] text-rose-300 border-rose-500/20';
}

function badgeLabel(badge: LeadDetailResponse['badge'], last_updated?: string) {
  if (badge === 'new_today') {
    const todayStr = new Date().toISOString().split('T')[0];
    const leadDateStr = last_updated ? new Date(last_updated).toISOString().split('T')[0] : todayStr;
    if (leadDateStr === todayStr) {
      return 'New Today';
    }
    return null; // Automatically expires at midnight on a new calendar day
  }
  if (badge === 'score_up') return 'Score Up';
  if (badge === 'score_down') return 'Score Down';
  if (badge === 'signal_added') return 'Signal Added';
  return null;
}

function badgeClass(badge: LeadDetailResponse['badge']) {
  if (badge === 'new_today') return 'border-[var(--nexa-accent)] bg-[var(--nexa-accent-dim)] text-[var(--nexa-accent)]';
  if (badge === 'score_up') return 'border-emerald-500/30 bg-[var(--nexa-emerald-dim)] text-emerald-300';
  if (badge === 'score_down') return 'border-rose-500/30 bg-[var(--nexa-rose-dim)] text-rose-300';
  return 'border-[var(--nexa-accent)]/30 bg-[var(--nexa-accent-dim)] text-[var(--nexa-accent-bright)]';
}

function getHiringNuance(lead: LeadDetailResponse) {
  const signalText = (lead.signals || []).map(s => (s.signal_type + ' ' + s.verbatim_quote).toLowerCase()).join(' ');
  const whyNowText = (lead.why_now || '').toLowerCase();
  const fullText = signalText + ' ' + whyNowText;

  if (fullText.includes('sdr') || fullText.includes('sales reps') || fullText.includes('adjacent') || fullText.includes('engineers') || (fullText.includes('hiring') && !fullText.includes('marketing manager'))) {
    return { label: 'Adjacent Hiring', type: 'adjacent', desc: 'High Intent: Hiring sales/engineers, missing marketing/recruiting' };
  } else if (fullText.includes('hiring marketing') || fullText.includes('marketing lead') || fullText.includes('direct hiring')) {
    return { label: 'Direct Hiring', type: 'direct', desc: 'Medium Intent: Building in-house marketing team' };
  }
  return { label: 'Expansion Mode', type: 'general', desc: 'General hiring & growth velocity' };
}

function formatEmployeeCount(count: number | null): string {
  if (!count) return '120 emp';
  if (count >= 1000) {
    const inK = count / 1000;
    return `${inK % 1 === 0 ? inK : inK.toFixed(1)}K emp`;
  }
  return `${count} emp`;
}

function getFirstSentence(text?: string): string {
  if (!text) return 'Intent signals detected for target company.';
  const clean = text.trim();
  const firstSentence = clean.split(/(?<=[.!?])\s+/)[0];
  return firstSentence || clean;
}

function getLeadScore(lead: LeadDetailResponse): number {
  if (lead.badge === 'filtered' || lead.ai_verdict?.includes('API Error')) {
    return 0;
  }
  return lead.intent_score ?? lead.icp_score ?? 0;
}

function getSignalBadgeStyle(signalText: string) {
  const lower = signalText.toLowerCase();

  // 1. Funding round / Series / Seed / Revenue -> Indigo theme
  if (lower.includes('fund') || lower.includes('series') || lower.includes('seed') || lower.includes('$')) {
    return 'border border-indigo-300 bg-indigo-100 text-indigo-900 dark:border-indigo-500/40 dark:bg-indigo-950/80 dark:text-indigo-300 font-mono font-bold shadow-xs';
  }

  // 2. Headcount / Growth / Revenue % -> Emerald theme
  if (lower.includes('headcount') || lower.includes('growth') || lower.includes('%') || lower.includes('+') || lower.includes('expansion')) {
    return 'border border-emerald-300 bg-emerald-100 text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-950/80 dark:text-emerald-300 font-mono font-bold shadow-xs';
  }

  // 3. Roles / SDR / Hiring Gap / Hiring -> Amber theme
  if (lower.includes('role') || lower.includes('sdr') || lower.includes('hire') || lower.includes('gap')) {
    return 'border border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/80 dark:text-amber-300 font-mono font-bold shadow-xs';
  }

  // 4. Executive Hires (CMO, VP Sales) -> Purple theme
  if (lower.includes('cmo') || lower.includes('vp') || lower.includes('exec') || lower.includes('director')) {
    return 'border border-purple-300 bg-purple-100 text-purple-900 dark:border-purple-500/40 dark:bg-purple-950/80 dark:text-purple-300 font-mono font-bold shadow-xs';
  }

  // 5. Agency / Partnership / Intent post -> Teal theme
  if (lower.includes('agency') || lower.includes('partner') || lower.includes('post') || lower.includes('seek')) {
    return 'border border-teal-300 bg-teal-100 text-teal-900 dark:border-teal-500/40 dark:bg-teal-950/80 dark:text-teal-300 font-mono font-bold shadow-xs';
  }

  // 6. Ads paused / Meta ads -> Rose theme
  if (lower.includes('ad') || lower.includes('meta') || lower.includes('pause') || lower.includes('stop')) {
    return 'border border-rose-300 bg-rose-100 text-rose-900 dark:border-rose-500/40 dark:bg-rose-950/80 dark:text-rose-300 font-mono font-bold shadow-xs';
  }

  return 'border border-teal-300 bg-teal-100 text-teal-900 dark:border-teal-500/30 dark:bg-teal-950/60 dark:text-teal-300 font-mono font-bold shadow-xs';
}

export default function LeadTable({
  leads,
  scannedLeads = [],
  setScannedLeads,
  selectedLeadId,
  onSelectLead,
  onLeadIngested,
  onLeadDeleted,
  status,
  externalSearchTerm = '',
  isPipelineTab = false,
  isTrackRecordsTab = false,
  trackedLeadIds = [],
  onToggleTrackLead
}: LeadTableProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTier, setSelectedTier] = useState<LeadTier | 'ALL'>('ALL');
  const [dateFilter, setDateFilter] = useState<'ALL' | 'TODAY' | '7DAYS' | '30DAYS'>('ALL');
  const [scoreFilter, setScoreFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [signalFilter, setSignalFilter] = useState<'ALL' | 'HIRING' | 'FUNDING' | 'HEADCOUNT'>('ALL');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [pitcherLead, setPitcherLead] = useState<LeadDetailResponse | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [expandedContacts, setExpandedContacts] = useState<Record<string, boolean>>({});

  const filterContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (filterContainerRef.current && !filterContainerRef.current.contains(event.target as Node)) {
        setIsFilterOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (selectedTier !== 'ALL') count++;
    if (dateFilter !== 'ALL') count++;
    if (scoreFilter !== 'ALL') count++;
    if (signalFilter !== 'ALL') count++;
    return count;
  }, [selectedTier, dateFilter, scoreFilter, signalFilter]);

  const [noLeadsAlert, setNoLeadsAlert] = useState<{
    isOpen: boolean;
    processedCount: number;
    message: string;
  } | null>(null);

  const handleRunPipeline = async () => {
    setIsPipelineRunning(true);
    try {
      const existingIds = new Set(leads.map((l) => String(l.id || l.domain || l.company_name)));
      const res = await runPipeline();
      const freshLeads = await fetchLeads();

      if (onLeadIngested && freshLeads.length > 0) {
        freshLeads.forEach((l) => onLeadIngested(l));
      }

      // Determine the 5 new/fresh pipeline results
      const newItems = freshLeads.filter((l) => !existingIds.has(String(l.id || l.domain || l.company_name)));
      
      const qualifiedCount = res?.qualified_count ?? 0;
      if (qualifiedCount === 0 || (newItems.length === 0 && (!res?.qualified_leads || res.qualified_leads.length === 0))) {
        setNoLeadsAlert({
          isOpen: true,
          processedCount: res?.processed_count || 5,
          message: `Scanned ${res?.processed_count || 5} candidate companies in this batch, but all leads had intent scores below 80 and were disqualified.`
        });
      }

      const itemsToStore = newItems.length >= 5 ? newItems.slice(0, 5) : (newItems.length > 0 ? newItems : freshLeads.slice(0, 5));

      if (setScannedLeads) {
        setScannedLeads(itemsToStore);
      }
    } catch (e) {
      console.error('Pipeline execution failed:', e);
    } finally {
      setIsPipelineRunning(false);
    }
  };

  const handleScan = async () => {
    if (!searchTerm.trim()) return;
    setIsScanning(true);

    // Enforce a minimum 5-second delay for the hacker animation
    const minDelay = new Promise(resolve => setTimeout(resolve, 5000));

    try {
      const targetDomain = searchTerm.trim();
      const [newLead] = await Promise.all([
        ingestLead(targetDomain),
        minDelay
      ]);

      if (onLeadIngested) {
        onLeadIngested(newLead);
      }
    } catch (e) {
      console.error('Ingestion failed', e);
      alert('Failed to ingest company.');
    } finally {
      setIsScanning(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteLead(id);
      setConfirmDeleteId(null);
      if (onLeadDeleted) {
        onLeadDeleted(id);
      }
    } catch (e) {
      console.error('Deletion failed', e);
      alert('Failed to delete company.');
    }
  };

  const selectedLead = useMemo(() => {
    if (!selectedLeadId) return null;
    const key = String(selectedLeadId);
    return scannedLeads.find((l) => String(l.id || l.domain || l.company_name) === key) ||
           leads.find((l) => String(l.id || l.domain || l.company_name) === key) ||
           null;
  }, [leads, scannedLeads, selectedLeadId]);


  const filteredLeads = useMemo(() => {
    const baseSource = isPipelineTab ? scannedLeads : leads;

    const activeSearch = (externalSearchTerm || searchTerm).toLowerCase().trim();
    const todayStr = new Date().toISOString().split('T')[0];
    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);

    return baseSource.filter((lead) => {
      // 1. Search Query
      const matchesSearch = !activeSearch ||
        lead.company_name.toLowerCase().includes(activeSearch) ||
        lead.industry.toLowerCase().includes(activeSearch) ||
        lead.domain.toLowerCase().includes(activeSearch) ||
        (lead.why_now && lead.why_now.toLowerCase().includes(activeSearch));

      // 2. Tier Filter
      const matchesTier = selectedTier === 'ALL' || lead.tier === selectedTier;

      // 3. Date / Recency Filter
      let matchesDate = true;
      if (dateFilter === 'TODAY') {
        const startOfToday = new Date();
        startOfToday.setHours(0, 0, 0, 0);
        const leadTime = lead.last_updated ? new Date(lead.last_updated).getTime() : 0;
        matchesDate = leadTime >= startOfToday.getTime() || lead.badge === 'new_today';
      } else if (dateFilter === '7DAYS') {
        const leadTime = lead.last_updated ? new Date(lead.last_updated).getTime() : 0;
        matchesDate = leadTime >= sevenDaysAgo.getTime() || lead.badge === 'new_today';
      } else if (dateFilter === '30DAYS') {
        const leadTime = lead.last_updated ? new Date(lead.last_updated).getTime() : 0;
        matchesDate = leadTime >= thirtyDaysAgo.getTime() || lead.badge === 'new_today';
      }

      // 4. Score Filter (Hot >= 70, Warm 40-69, Watching < 40)
      let matchesScore = true;
      const leadScore = getLeadScore(lead);
      if (scoreFilter === 'HIGH') matchesScore = leadScore >= 70;
      else if (scoreFilter === 'MEDIUM') matchesScore = leadScore >= 40 && leadScore < 70;
      else if (scoreFilter === 'LOW') matchesScore = leadScore < 40;

      // 5. Signal Filter
      let matchesSignal = true;
      if (signalFilter !== 'ALL') {
        const tagStr = (lead.signal_tags || []).map(t => (t.tag || '').toLowerCase()).join(' ');
        const verbatimStr = (lead.signals || []).map(s => (s.signal_type || '') + ' ' + (s.verbatim_quote || '')).join(' ').toLowerCase();
        const fundingStageStr = (lead.funding_stage || '').toLowerCase();
        const socialSegStr = (lead.social_segment || '').toLowerCase();
        const whyNowStr = (lead.why_now || '').toLowerCase();
        const verdictStr = (lead.ai_verdict || '').toLowerCase();

        const signalsStr = `${tagStr} ${verbatimStr} ${fundingStageStr} ${socialSegStr} ${whyNowStr} ${verdictStr}`;

        if (signalFilter === 'HIRING') {
          matchesSignal = signalsStr.includes('hiring') || signalsStr.includes('sdr') || signalsStr.includes('role') || signalsStr.includes('hire') || signalsStr.includes('recruit');
        } else if (signalFilter === 'FUNDING') {
          matchesSignal = signalsStr.includes('fund') || signalsStr.includes('series') || signalsStr.includes('seed') || signalsStr.includes('raised') || signalsStr.includes('$') || signalsStr.includes('capital') || signalsStr.includes('venture');
        } else if (signalFilter === 'HEADCOUNT') {
          matchesSignal = !!lead.employee_count || signalsStr.includes('headcount') || signalsStr.includes('growth') || signalsStr.includes('expansion') || signalsStr.includes('employee');
        }
      }

      return matchesSearch && matchesTier && matchesDate && matchesScore && matchesSignal;
    }).sort((a, b) => {
      // Always score-descending within each bucket. Never surface the weakest lead first.
      const scoreA = getLeadScore(a);
      const scoreB = getLeadScore(b);
      if (scoreB !== scoreA) {
        return scoreB - scoreA; // Highest score first
      }
      return (b.confidence?.verified ?? 0) - (a.confidence?.verified ?? 0);
    });
  }, [leads, scannedLeads, searchTerm, externalSearchTerm, selectedTier, dateFilter, scoreFilter, signalFilter, isPipelineTab]);

  return (
    <div className="flex flex-col gap-4 flex-1 min-h-0">
      {/* Pipeline Tab Hero Banner (Find leads UI matching reference image & white-theme configured) */}
      {isPipelineTab && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#F2FBF6] dark:bg-[#071D12] p-5 sm:p-6 rounded-2xl sm:rounded-3xl border border-[#D1F3E0] dark:border-[#0D3823] shadow-xs">
          <div className="flex items-start sm:items-center gap-3.5">
            <div className="w-9 h-9 rounded-xl border border-emerald-300 dark:border-emerald-500/80 bg-white dark:bg-emerald-950/40 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0 shadow-2xs mt-0.5 sm:mt-0">
              <Podcast size={18} className="stroke-[2.3]" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">
                  Find leads
                </h1>
                {isPipelineRunning ? (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 dark:bg-blue-950/80 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-800/50 shadow-2xs flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse shrink-0" />
                    Searching
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 dark:bg-[#0D281A] text-emerald-800 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/40 shadow-2xs">
                    Ready to run
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-600 dark:text-zinc-400 font-medium leading-relaxed">
                Scans social platforms, job boards, and company data continuously to surface new companies showing buying signals.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end sm:self-center shrink-0">
            <button
              type="button"
              onClick={handleRunPipeline}
              disabled={isPipelineRunning}
              className={`px-4 py-2 rounded-xl border font-bold text-xs shadow-2xs transition-all duration-200 flex items-center gap-2 ${
                isPipelineRunning
                  ? 'border-slate-300 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-800/80 cursor-not-allowed text-slate-500 dark:text-zinc-400'
                  : 'border-emerald-300 dark:border-[#0D3823] bg-white dark:bg-[#0A2617] text-slate-800 dark:text-white hover:bg-emerald-50 dark:hover:bg-[#0E3520] hover:scale-[1.02] active:scale-[0.98]'
              }`}
            >
              {isPipelineRunning ? (
                <Loader2 size={14} className="animate-spin text-slate-500 dark:text-zinc-400 shrink-0" />
              ) : (
                <Podcast size={14} className="stroke-[2.3] text-emerald-600 dark:text-emerald-400 shrink-0" />
              )}
              <span>{isPipelineRunning ? 'Searching...' : 'Find leads'}</span>
            </button>
          </div>
        </div>
      )}

      {/* Track Records Tab Hero Banner */}
      {isTrackRecordsTab && (
        <div className="nexa-card nexa-card-no-hover p-4 sm:p-7 rounded-2xl sm:rounded-3xl border border-[#FDE68A] dark:border-amber-500/30 bg-[#FFFDF5] dark:bg-gradient-to-r dark:from-amber-950/40 dark:via-slate-900/80 dark:to-amber-950/40 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 sm:gap-5 shadow-xs">
          <div className="flex items-center gap-3 sm:gap-4 text-left">
            <div className="flex h-10 w-10 sm:h-13 sm:w-13 shrink-0 items-center justify-center rounded-2xl bg-white dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-500/40 shadow-2xs">
              <Bookmark size={22} className="sm:w-7 sm:h-7" />
            </div>
            <div>
              <h2 className="text-sm sm:text-lg font-black text-slate-900 dark:text-zinc-100 flex flex-wrap items-center gap-2">
                Track Leads & Active Watchlist
                <span className="text-[9px] sm:text-[10px] font-bold uppercase tracking-wider text-amber-800 dark:text-amber-400 bg-amber-100 dark:bg-amber-950/60 px-2 py-0.5 rounded-full border border-amber-300 dark:border-amber-500/30">
                  {leads.length} Tracked
                </span>
              </h2>
              <p className="text-[11px] sm:text-xs text-slate-600 dark:text-zinc-400 mt-1 font-medium max-w-xl">
                High-intent prospects and target companies saved on your active watchlist.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Table Section Header */}
      {!isPipelineTab && !isTrackRecordsTab && (
        <div className="flex items-center justify-between px-1 pt-1 pb-0.5">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-zinc-300">
              Live Target Leads & Signal Grid
            </h3>
            <span className="text-[10px] font-semibold text-slate-500 dark:text-zinc-500">
              ({filteredLeads.length} companies)
            </span>
          </div>
          <span className="text-[11px] font-medium text-slate-500 dark:text-zinc-400 hidden sm:inline">
            Click any company row to inspect signals & AI pitch
          </span>
        </div>
      )}

      {/* Data Grid Card — Nexa Design System Styling */}
      <div className="nexa-card nexa-card-no-hover overflow-hidden flex-1 flex flex-col min-h-0 relative">
        {(isScanning || isPipelineRunning) && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-white/95 dark:bg-nexa-bg/95 backdrop-blur-md p-4 overflow-y-auto rounded-2xl">
            <DocumentMagnifierScan />
          </div>
        )}

        {/* Mobile Horizontal Scroll Hint */}
        <div className="text-[10px] font-bold text-slate-500 dark:text-zinc-400 px-3 py-1 flex items-center justify-between sm:hidden bg-slate-100/60 dark:bg-white/5 border-b border-nexa-border">
          <span>Swipe grid sideways to view details</span>
          <span>→</span>
        </div>

        <div className="overflow-x-auto flex-1">
          <table className="w-full min-w-[920px] border-collapse text-left">
            <thead>
              <tr className="border-b border-slate-200/80 dark:border-white/10 bg-slate-50/70 dark:bg-white/5 text-[11px] font-black uppercase tracking-wider text-slate-700 dark:text-zinc-300">
                <th className="p-4 text-left min-w-[200px]">COMPANY</th>
                <th className="p-4 text-center min-w-[90px]">SCORE</th>
                <th className="p-4 text-center min-w-[240px]">SIGNALS</th>
                <th className="p-4 text-center min-w-[320px]">WHY NOW</th>
                <th className="p-4 text-center min-w-[120px] relative">
                  <div ref={filterContainerRef} className="relative flex justify-center">
                    <button
                      type="button"
                      onClick={() => setIsFilterOpen(!isFilterOpen)}
                      className={`flex h-[28px] items-center gap-1.5 rounded-lg border px-2.5 text-[11px] font-bold transition shadow-xs ${activeFilterCount > 0
                        ? 'border-emerald-500/50 bg-emerald-50 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                        : 'border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-white/5 text-slate-800 dark:text-zinc-300 hover:bg-slate-200/80 dark:hover:bg-white/10 hover:text-slate-950 dark:hover:text-white'
                        }`}
                      title="Filter Companies"
                    >
                      <SlidersHorizontal size={13} />
                      <span>Filter</span>
                      {activeFilterCount > 0 && (
                        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-black text-zinc-950">
                          {activeFilterCount}
                        </span>
                      )}
                    </button>

                    {/* Filter Popover Modal */}
                    {isFilterOpen && (
                      <div className="filter-popover absolute right-0 top-full mt-1 w-72 sm:w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 dark:border-nexa-border bg-white dark:bg-[#181824] p-4 shadow-2xl z-50 text-left normal-case tracking-normal animate-in fade-in slide-in-from-top-2">
                        <div className="flex items-center justify-between border-b border-slate-100 dark:border-white/10 pb-2.5 mb-3">
                          <div className="flex items-center gap-2">
                            <Filter size={15} className="text-emerald-500" />
                            <span className="text-xs font-bold text-slate-900 dark:text-zinc-100">Filter Leads</span>
                          </div>
                          {activeFilterCount > 0 && (
                            <button
                              type="button"
                              onClick={() => {
                                setDateFilter('ALL');
                                setScoreFilter('ALL');
                                setSignalFilter('ALL');
                                setSelectedTier('ALL');
                              }}
                              className="text-[11px] font-bold text-rose-500 hover:underline"
                            >
                              Reset All
                            </button>
                          )}
                        </div>

                        {/* Filter Option 1: Recency / Date */}
                        <div className="mb-3.5">
                          <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1.5 block">
                            Date Discovered
                          </label>
                          <div className="grid grid-cols-2 gap-1.5">
                            {[
                              { id: 'ALL', label: 'All Time' },
                              { id: 'TODAY', label: 'Added Today' },
                              { id: '7DAYS', label: 'Past 7 Days' },
                              { id: '30DAYS', label: 'Past 30 Days' }
                            ].map((opt) => (
                              <button
                                key={opt.id}
                                type="button"
                                onClick={() => setDateFilter(opt.id as any)}
                                className={`rounded-xl px-2.5 py-1.5 text-[11px] font-medium transition ${dateFilter === opt.id
                                  ? 'filter-btn-active bg-emerald-600 text-white font-extrabold shadow-xs'
                                  : 'filter-btn-inactive border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-white/10'
                                  }`}
                              >
                                {opt.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Filter Option 2: Score Range */}
                        <div className="mb-3.5">
                          <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1.5 block">
                            ICP Score Range
                          </label>
                          <div className="grid grid-cols-2 gap-1.5">
                            {[
                              { id: 'ALL', label: 'All Scores' },
                              { id: 'HIGH', label: 'High (80+)' },
                              { id: 'MEDIUM', label: 'Medium (60-80)' },
                              { id: 'LOW', label: 'Low (<60)' }
                            ].map((opt) => (
                              <button
                                key={opt.id}
                                type="button"
                                onClick={() => setScoreFilter(opt.id as any)}
                                className={`rounded-xl px-2.5 py-1.5 text-[11px] font-medium transition ${scoreFilter === opt.id
                                  ? 'filter-btn-active bg-emerald-600 text-white font-extrabold shadow-xs'
                                  : 'filter-btn-inactive border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-white/10'
                                  }`}
                              >
                                {opt.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Filter Option 3: Signal Category */}
                        <div>
                          <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1.5 block">
                            Signal Type
                          </label>
                          <div className="grid grid-cols-2 gap-1.5">
                            {[
                              { id: 'ALL', label: 'All Signals' },
                              { id: 'HIRING', label: 'SDR Hiring' },
                              { id: 'FUNDING', label: 'Funding News' },
                              { id: 'HEADCOUNT', label: 'Headcount Growth' }
                            ].map((opt) => (
                              <button
                                key={opt.id}
                                type="button"
                                onClick={() => setSignalFilter(opt.id as any)}
                                className={`rounded-xl px-2.5 py-1.5 text-[11px] font-medium transition ${signalFilter === opt.id
                                  ? 'filter-btn-active bg-emerald-600 text-white font-extrabold shadow-xs'
                                  : 'filter-btn-inactive border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-white/10'
                                  }`}
                              >
                                {opt.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {isPipelineRunning ? (
                <tr>
                  <td colSpan={5} className="p-4 sm:p-6 bg-slate-950/40">
                    <DocumentMagnifierScan />
                  </td>
                </tr>
              ) : (
                <>
                  {filteredLeads.map((lead) => {
                    const leadKey = String(lead.id || lead.domain || lead.company_name);
                    const isSelected = String(selectedLeadId) === leadKey;
                    return (
                      <Fragment key={leadKey}>
                        <tr
                          onClick={() => onSelectLead(isSelected ? null : leadKey)}
                          className={`nexa-row-hover border-b border-nexa-border cursor-pointer transition-colors ${isSelected ? 'bg-[var(--nexa-accent-dim)]' : ''
                            }`}
                        >
                          {/* COMPANY */}
                          <td className="p-4 font-medium text-zinc-100 text-left">
                            <div className="flex flex-col items-start gap-0.5 text-left group">
                              <span className="font-bold text-zinc-100 text-sm group-hover:text-[var(--nexa-accent)] transition-colors">
                                {lead.company_name}
                              </span>
                              <span className="text-xs text-zinc-400 font-normal">
                                {(!lead.industry || lead.industry === 'Unknown') ? 'SaaS' : lead.industry}{lead.funding_stage ? ` · ${lead.funding_stage}` : ''} · {formatEmployeeCount(lead.employee_count)}
                              </span>
                            </div>
                          </td>

                          {/* SCORE */}
                          <td className="p-4 text-center">
                            {(() => {
                              const displayScore = getLeadScore(lead);
                              const scoreColor = displayScore >= 70
                                ? 'bg-emerald-100 text-emerald-900 border border-emerald-300 dark:bg-emerald-950/80 dark:text-emerald-400 dark:border-emerald-500/40'
                                : displayScore >= 40
                                  ? 'bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950/80 dark:text-amber-400 dark:border-amber-500/40'
                                  : 'bg-rose-100 text-rose-900 border border-rose-300 dark:bg-rose-950/80 dark:text-rose-400 dark:border-rose-500/40';

                              return (
                                <span className={`inline-flex items-center justify-center rounded-full px-3 py-1 text-xs font-bold font-mono ${scoreColor}`}>
                                  {displayScore}
                                </span>
                              );
                            })()}
                          </td>

                          {/* SIGNALS */}
                          <td className="p-4 text-center">
                            <div className="flex flex-wrap gap-1.5 items-center justify-center max-w-xs">
                              {(() => {
                                const signalPills: Array<{ label: string; style: string }> = [];

                                // 1. Backend Signal Tags (from Groq / intent extraction)
                                if (lead.signal_tags && lead.signal_tags.length > 0) {
                                  lead.signal_tags.forEach((st) => {
                                    if (st.tag && !signalPills.some((p) => p.label.toLowerCase() === st.tag.toLowerCase())) {
                                      signalPills.push({
                                        label: st.tag,
                                        style: getSignalBadgeStyle(st.tag)
                                      });
                                    }
                                  });
                                }

                                // 2. Funding Stage
                                if (lead.funding_stage && lead.funding_stage !== 'UNKNOWN') {
                                  const fLabel = lead.funding_stage.includes('Series') || lead.funding_stage.includes('Seed')
                                    ? lead.funding_stage
                                    : `${lead.funding_stage} Round`;
                                  if (!signalPills.some((p) => p.label.toLowerCase() === fLabel.toLowerCase())) {
                                    signalPills.push({ label: fLabel, style: getSignalBadgeStyle(fLabel) });
                                  }
                                }

                                // 3. Extracted Verbatim Signals (from Groq)
                                (lead.signals || []).forEach((s) => {
                                  const rawLabel = s.signal_type.replace(/_/g, ' ');
                                  const formattedLabel = rawLabel.charAt(0).toUpperCase() + rawLabel.slice(1);
                                  if (!signalPills.some((p) => p.label.toLowerCase() === formattedLabel.toLowerCase())) {
                                    signalPills.push({
                                      label: formattedLabel,
                                      style: getSignalBadgeStyle(s.signal_type + ' ' + (s.verbatim_quote || ''))
                                    });
                                  }
                                });

                                // 4. Employee Count (Real count from DB if available)
                                if (lead.employee_count && signalPills.length < 3) {
                                  const empLabel = `${lead.employee_count} employees`;
                                  if (!signalPills.some((p) => p.label.toLowerCase() === empLabel.toLowerCase())) {
                                    signalPills.push({
                                      label: empLabel,
                                      style: getSignalBadgeStyle('growth')
                                    });
                                  }
                                }

                                return signalPills.slice(0, 3).map((pill, idx) => (
                                  <span
                                    key={idx}
                                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wider uppercase font-mono ${pill.style}`}
                                  >
                                    <Sparkles size={10} />
                                    {pill.label}
                                  </span>
                                ));
                              })()}
                            </div>
                          </td>

                          {/* WHY NOW */}
                          <td className="p-4 text-xs text-zinc-300 text-left leading-snug max-w-sm">
                            <div className="flex flex-col gap-1 text-left">
                              {(() => {
                                const whyNowText = lead.one_line_reason || (lead.why_now && lead.why_now !== 'Intent signals detected'
                                  ? lead.why_now
                                  : getFirstSentence(lead.ai_verdict));
                                return (
                                  <span className="line-clamp-3 text-zinc-300 font-medium leading-relaxed">
                                    {whyNowText}
                                  </span>
                                );
                              })()}
                            </div>
                          </td>

                          {/* ACTIONS */}
                          <td className="p-4 text-center">
                            <div className="flex items-center justify-center gap-2" onClick={(e) => e.stopPropagation()}>
                              <button
                                type="button"
                                onClick={() => onToggleTrackLead?.(leadKey)}
                                className={`rounded-xl border p-2 transition shadow-xs ${(trackedLeadIds || []).includes(leadKey) || (trackedLeadIds || []).includes(lead.domain) || (trackedLeadIds || []).includes(lead.company_name)
                                    ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400 font-bold'
                                    : 'border-slate-200 bg-slate-100 text-slate-400 dark:border-white/10 dark:bg-white/5 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-200 dark:hover:bg-white/10'
                                  }`}
                                title={
                                  (trackedLeadIds || []).includes(leadKey) || (trackedLeadIds || []).includes(lead.domain) || (trackedLeadIds || []).includes(lead.company_name)
                                    ? 'Tracked in Track Leads (Click to untrack)'
                                    : 'Click to Track Company'
                                }
                              >
                                <Bookmark size={15} className={(trackedLeadIds || []).includes(leadKey) || (trackedLeadIds || []).includes(lead.domain) || (trackedLeadIds || []).includes(lead.company_name) ? 'fill-emerald-400 text-emerald-400' : ''} />
                              </button>

                              {confirmDeleteId === String(lead.id || lead.domain || lead.company_name) ? (
                                <div className="flex items-center gap-1.5">
                                  <button
                                    type="button"
                                    onClick={() => handleDelete(String(lead.id || lead.domain || lead.company_name))}
                                    className="rounded-lg bg-rose-600 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-rose-500 transition shadow-xs"
                                  >
                                    Confirm
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setConfirmDeleteId(null)}
                                    className="rounded-lg border border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-slate-700 px-2.5 py-1 text-[11px] font-bold transition"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => setConfirmDeleteId(String(lead.id || lead.domain || lead.company_name))}
                                  className="rounded-xl border border-rose-200 bg-rose-50 p-2 text-rose-600 hover:bg-rose-100 hover:text-rose-700 dark:border-rose-500/30 dark:bg-rose-950/40 dark:text-rose-400 dark:hover:bg-rose-900/60 dark:hover:text-rose-200 transition shadow-xs"
                                  title="Delete Lead"
                                >
                                  <Trash2 size={15} />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      </Fragment>
                    );
                  })}
                  {(filteredLeads.length === 0 || status === 'error') && (
                    <tr>
                      <td
                        className="p-16 text-center text-sm font-medium text-slate-500"
                        colSpan={5}
                      >
                        {isPipelineTab ? (
                          <div className="flex flex-col items-center justify-center py-16 space-y-4 max-w-md mx-auto">
                            <div className="w-14 h-14 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-700/60 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shadow-sm mb-1">
                              <Podcast size={28} className="stroke-[2.2]" />
                            </div>
                            <div className="space-y-1.5">
                              <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100 tracking-tight">
                                No leads yet
                              </h3>
                              <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-xs mx-auto leading-relaxed font-normal">
                                Run your first search to start discovering companies showing buying signals.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={handleRunPipeline}
                              disabled={isPipelineRunning}
                              className="mt-2 px-4 py-2 rounded-xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-700 text-slate-800 dark:text-zinc-200 font-bold text-xs flex items-center gap-2 transition-all shadow-2xs"
                            >
                              {isPipelineRunning ? (
                                <Loader2 size={13} className="animate-spin text-slate-500 dark:text-zinc-400 shrink-0" />
                              ) : (
                                <Podcast size={13} className="stroke-[2.3] text-emerald-600 dark:text-emerald-400 shrink-0" />
                              )}
                              <span>{isPipelineRunning ? 'Searching...' : 'Find leads'}</span>
                            </button>
                          </div>
                        ) : status === 'error' ? (
                          <div className="flex flex-col items-center justify-center gap-3 py-6">
                            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500 border border-amber-500/20 shadow-xs">
                              <X size={22} />
                            </div>
                            <h3 className="text-base font-extrabold text-slate-800 dark:text-zinc-100">
                              Can't fetch data, system not online
                            </h3>
                            <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-sm font-medium">
                              The backend API server is offline. As soon as the network becomes online, the company data will populate automatically.
                            </p>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center gap-4">
                            <p>No tracking records found matching the active filters.</p>
                            <button
                              type="button"
                              onClick={handleRunPipeline}
                              disabled={isPipelineRunning}
                              className="rounded-lg bg-[var(--nexa-accent)] px-6 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-[var(--nexa-accent-glow)] shadow-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                              {isPipelineRunning ? (
                                <>
                                  <Loader2 size={16} className="animate-spin" />
                                  <span>Running Pipeline...</span>
                                </>
                              ) : (
                                <span>Run Base Discovery Pipeline</span>
                              )}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {pitcherLead ? (
        <PitcherMode
          id={pitcherLead.id}
          company_name={pitcherLead.company_name}
          onClose={() => setPitcherLead(null)}
        />
      ) : null}

      {/* Dynamic Slide-Over Side Drawer from Right */}
      <LeadDetailDrawer
        lead={selectedLead}
        allLeads={filteredLeads}
        onSelectLead={onSelectLead}
        onClose={() => onSelectLead(null)}
        isTracked={
          selectedLead
            ? trackedLeadIds.includes(String(selectedLead.id || selectedLead.domain || selectedLead.company_name)) ||
            trackedLeadIds.includes(selectedLead.domain) ||
            trackedLeadIds.includes(selectedLead.company_name)
            : false
        }
        onToggleTrack={() => {
          if (selectedLead) {
            const key = String(selectedLead.id || selectedLead.domain || selectedLead.company_name);
            onToggleTrackLead?.(key);
          }
        }}
      />

      {/* Custom Glassmorphic Alert Box for Disqualified Batch */}
      {noLeadsAlert?.isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 backdrop-blur-md animate-in fade-in duration-200 p-4">
          <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-amber-500/30 bg-zinc-950/95 p-6 shadow-2xl shadow-amber-950/50 text-left backdrop-blur-2xl">
            {/* Ambient background glow */}
            <div className="absolute -top-12 -right-12 h-32 w-32 rounded-full bg-amber-500/15 blur-2xl pointer-events-none" />
            
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-400">
                <Workflow className="h-6 w-6" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold tracking-tight text-zinc-100">
                    No Qualified Leads in Batch
                  </h3>
                  <button
                    type="button"
                    onClick={() => setNoLeadsAlert(null)}
                    className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-zinc-300">
                  {noLeadsAlert.message}
                </p>
                <div className="mt-4 rounded-xl bg-zinc-900/90 border border-zinc-800 p-3 text-xs text-zinc-400">
                  <strong className="text-zinc-200 block mb-0.5">💡 Disqualification Rule:</strong>
                  Only leads scoring <span className="text-amber-400 font-bold">80 or above</span> pass qualification. Scores below 80 are automatically discarded.
                </div>
                <div className="mt-5 flex justify-end">
                  <button
                    type="button"
                    onClick={() => setNoLeadsAlert(null)}
                    className="rounded-xl bg-amber-500 hover:bg-amber-400 text-zinc-950 px-5 py-2 text-xs font-bold tracking-wide transition shadow-md shadow-amber-500/20"
                  >
                    Dismiss Alert
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
