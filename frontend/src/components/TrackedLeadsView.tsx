import React, { useState, useMemo, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  Plus, 
  ExternalLink, 
  Briefcase, 
  Users, 
  MapPin, 
  Calendar,
  Signal,
  LineChart,
  Link as LinkIcon,
  ChevronLeft, 
  ChevronRight,
  Mail,
  Linkedin
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { LeadDetailResponse } from '../types/lead';
import JobsTab from './JobsTab';

interface TrackedLeadsViewProps {
  leads: LeadDetailResponse[];
  selectedLeadId: string | null;
  onSelectLead: (id: string | null) => void;
  onToggleTrackLead?: (id: string) => void;
  onLeadDeleted?: (id: string) => void;
}

// Clean raw contact name string if formatted as markdown link
function cleanName(rawName: string): string {
  if (!rawName) return 'Executive Contact';
  return rawName
    .replace(/\[|\]\(https?:\/\/[^\)]+\)/g, '')
    .replace(/\[|\]/g, '')
    .trim();
}

// Format scan recency
function getScanTime(lastUpdated?: string): string {
  if (!lastUpdated) return '14h ago';
  const date = new Date(lastUpdated);
  const now = new Date();
  const diffHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));
  if (diffHours < 1) return '30m ago';
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export default function TrackedLeadsView({
  leads,
  selectedLeadId,
  onSelectLead,
}: TrackedLeadsViewProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTabFilter, setActiveTabFilter] = useState<'ALL' | 'HIGH' | 'ATTENTION'>('ALL');
  const [activeDetailTab, setActiveDetailTab] = useState<'signals' | 'insights' | 'jobs' | 'people'>('signals');
  const [currentPage, setCurrentPage] = useState(1);

  // Filter tracked companies
  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      const search = searchTerm.toLowerCase().trim();
      const matchesSearch =
        !search ||
        lead.company_name.toLowerCase().includes(search) ||
        lead.domain.toLowerCase().includes(search) ||
        lead.industry.toLowerCase().includes(search);

      const score = lead.intent_score ?? lead.icp_score ?? 0;
      const hasSignals = (lead.signals?.length || 0) > 0;
      if (activeTabFilter === 'HIGH') {
        return matchesSearch && hasSignals && score >= 70;
      }
      if (activeTabFilter === 'ATTENTION') {
        return matchesSearch && (score < 40 || lead.badge === 'filtered');
      }
      return matchesSearch;
    });
  }, [leads, searchTerm, activeTabFilter]);

  // Dynamic Pagination calculations
  const ITEMS_PER_PAGE = 8;
  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(filteredLeads.length / ITEMS_PER_PAGE));
  }, [filteredLeads]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(1);
    }
  }, [totalPages, currentPage]);

  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (safeCurrentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = Math.min(filteredLeads.length, startIndex + ITEMS_PER_PAGE);

  const paginatedLeads = useMemo(() => {
    return filteredLeads.slice(startIndex, endIndex);
  }, [filteredLeads, startIndex, endIndex]);

  // Selected Lead object
  const activeLead = useMemo(() => {
    if (!selectedLeadId && filteredLeads.length > 0) {
      return filteredLeads[0];
    }
    return (
      filteredLeads.find(
        (l) => String(l.id || l.domain || l.company_name) === String(selectedLeadId)
      ) || filteredLeads[0] || null
    );
  }, [filteredLeads, selectedLeadId]);

  const activeLeadKey = activeLead ? String(activeLead.id || activeLead.domain || activeLead.company_name) : '';

  // High signals count
  const highSignalsCount = useMemo(() => {
    return leads.filter((l) => (l.signals?.length || 0) > 0 && (l.intent_score ?? l.icp_score ?? 0) >= 70).length;
  }, [leads]);

  // Needs attention count
  const attentionCount = useMemo(() => {
    return leads.filter((l) => (l.intent_score ?? l.icp_score ?? 0) < 40 || l.badge === 'filtered').length;
  }, [leads]);

  // Counts for active lead
  const signalsCount = activeLead?.signals?.length || 0;
  const jobs = activeLead?.job_openings;
  const jobsList: any[] = (Array.isArray(jobs?.qualified_jobs) && jobs.qualified_jobs.length > 0)
    ? jobs.qualified_jobs
    : (Array.isArray(jobs?.verified_jobs) && jobs.verified_jobs.length > 0)
      ? jobs.verified_jobs
      : (Array.isArray(jobs?.jobs) && jobs.jobs.length > 0)
        ? jobs.jobs
        : (Array.isArray(jobs) && jobs.length > 0)
          ? jobs
          : (Array.isArray((activeLead as any)?.jobs) ? (activeLead as any).jobs : []);
  const jobsCount = jobsList.length;
  const contactsCount = activeLead?.contacts?.length || 0;

  const displayScore = activeLead ? (activeLead.intent_score ?? activeLead.icp_score ?? 0) : 0;
  const displayUrl = activeLead ? (activeLead.domain.startsWith('http') ? activeLead.domain : `https://${activeLead.domain}`) : '#';

  // Format initials for avatar
  const getInitials = (name: string) => {
    if (!name) return 'C';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <div className="flex flex-col gap-4 flex-1 min-h-0 w-full h-[calc(100vh-6.5rem)] overflow-hidden">
      {/* 1. TOP TITLE HEADER */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shrink-0">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
            Saved Leads
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 font-medium mt-0.5">
            Monitor saved target companies and track employee & intent changes every week
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            const domain = prompt('Enter target company domain (e.g. vercel.com):');
            if (domain) {
              alert(`Adding ${domain} to tracking pipeline...`);
            }
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/20 transition-all hover:scale-[1.02] active:scale-95 shrink-0"
        >
          <Plus size={16} />
          <span>Add Company</span>
        </button>
      </div>

      {/* 2. SPLIT LAYOUT CONTAINER */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0 overflow-hidden">
        
        {/* ============================================================ */}
        {/* LEFT COLUMN: COMPANY LIST PANEL (4 cols on lg) */}
        {/* ============================================================ */}
        <div className="lg:col-span-4 flex flex-col gap-3 rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-[#12121a] p-3.5 sm:p-4 shadow-sm h-full overflow-hidden">
          
          {/* Search Bar + Filter Button */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="relative flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
              <input
                type="text"
                placeholder="Search companies..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 pl-9 pr-3 py-2 text-xs font-semibold text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-500 outline-none focus:border-emerald-500 transition"
              />
            </div>
            <button
              type="button"
              className="p-2 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white transition"
              title="Filter Options"
            >
              <Filter size={15} />
            </button>
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 border-b border-slate-100 dark:border-white/10 pb-2 overflow-x-auto shrink-0">
            <button
              type="button"
              onClick={() => setActiveTabFilter('ALL')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTabFilter === 'ALL'
                  ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-white/5'
              }`}
            >
              <span>All Companies</span>
              <span className="px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-[10px] font-mono">
                {leads.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTabFilter('HIGH')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTabFilter === 'HIGH'
                  ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-white/5'
              }`}
            >
              <span>High Signals</span>
              <span className="px-1.5 py-0.2 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 text-[10px] font-mono border border-slate-200 dark:border-zinc-700">
                {highSignalsCount}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTabFilter('ATTENTION')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                activeTabFilter === 'ATTENTION'
                  ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-white/5'
              }`}
            >
              <span>Needs Attention</span>
              <span className="px-1.5 py-0.2 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 text-[10px] font-mono border border-slate-200 dark:border-zinc-700">
                {attentionCount}
              </span>
            </button>
          </div>

          {/* List Table Header */}
          <div className="grid grid-cols-12 px-2 py-1 text-[10px] font-black uppercase tracking-wider text-slate-400 dark:text-zinc-500 border-b border-slate-100 dark:border-white/5 shrink-0">
            <span className="col-span-6">COMPANY</span>
            <span className="col-span-3 text-center">SIGNALS</span>
            <span className="col-span-3 text-right">LAST SCAN</span>
          </div>

          {/* Scrollable Companies List */}
          <div className="flex-1 min-h-0 overflow-y-auto space-y-1.5 pr-1">
            {paginatedLeads.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400 dark:text-zinc-500">
                No tracked companies found matching filter.
              </div>
            ) : (
              paginatedLeads.map((lead) => {
                const leadKey = String(lead.id || lead.domain || lead.company_name);
                const isSelected = activeLeadKey === leadKey;
                const initials = getInitials(lead.company_name);
                const countSignals = lead.signals?.length || 0;
                const score = lead.intent_score ?? lead.icp_score ?? 0;

                return (
                  <div
                    key={leadKey}
                    onClick={() => onSelectLead(leadKey)}
                    className={`grid grid-cols-12 items-center p-2.5 rounded-xl cursor-pointer transition border ${
                      isSelected
                        ? 'border-emerald-500 bg-emerald-50/60 dark:bg-emerald-950/30 shadow-xs'
                        : 'border-transparent hover:border-slate-200 dark:hover:border-white/10 hover:bg-slate-50 dark:hover:bg-white/5'
                    }`}
                  >
                    {/* Left: Avatar & Company Info */}
                    <div className="col-span-6 flex items-center gap-2.5 min-w-0">
                      <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-mono font-black text-xs shrink-0 border ${
                        isSelected 
                          ? 'bg-emerald-600 text-white border-emerald-500' 
                          : 'bg-[#312E81] text-white border-indigo-900'
                      }`}>
                        {initials}
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="text-xs font-black text-slate-900 dark:text-zinc-100 truncate">
                          {lead.company_name}
                        </span>
                        <span className="text-[10px] font-medium text-slate-500 dark:text-zinc-400 truncate">
                          {lead.industry || 'Software'}
                        </span>
                      </div>
                    </div>

                    {/* Middle: Signal Pill */}
                    <div className="col-span-3 flex items-center justify-center gap-1">
                      <span className="px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400 text-[10px] font-mono font-bold">
                        {countSignals} signals
                      </span>
                    </div>

                    {/* Right: Last Scan Time */}
                    <div className="col-span-3 text-right">
                      <span className="text-[10px] font-mono font-medium text-slate-400 dark:text-zinc-500">
                        {getScanTime(lead.last_updated)}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Dynamic List Footer Pagination */}
          <div className="pt-2 border-t border-slate-100 dark:border-white/10 flex items-center justify-between text-[11px] font-medium text-slate-500 dark:text-zinc-400 shrink-0">
            <span>
              {filteredLeads.length === 0 ? 0 : startIndex + 1} - {endIndex} of {filteredLeads.length}
            </span>
            <div className="flex items-center gap-1 font-mono text-[10px]">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={safeCurrentPage === 1}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition"
                title="Previous Page"
              >
                <ChevronLeft size={13} />
              </button>

              {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
                <button
                  key={pageNum}
                  type="button"
                  onClick={() => setCurrentPage(pageNum)}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold transition ${
                    safeCurrentPage === pageNum
                      ? 'bg-emerald-500 text-white shadow-xs'
                      : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-white/10'
                  }`}
                >
                  {pageNum}
                </button>
              ))}

              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={safeCurrentPage === totalPages}
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition"
                title="Next Page"
              >
                <ChevronRight size={13} />
              </button>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* RIGHT COLUMN: COMPANY DETAIL PANEL (Exact Wireframe Match) */}
        {/* ============================================================ */}
        <div className="lg:col-span-8 flex flex-col gap-0 rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-[#F8FAFC] dark:bg-[#12121a] shadow-sm h-full overflow-hidden">
          {activeLead ? (
            <>
              {/* Top Company Header Card (Exact Wireframe Match) */}
              <div className="p-5 sm:p-6 bg-white dark:bg-[#12121a] border-b border-slate-200/80 dark:border-zinc-800 shrink-0 space-y-4">
                <div className="flex items-center gap-3.5">
                  {/* Purple/Indigo Initials Circle */}
                  <div className="w-12 h-12 rounded-full bg-[#312E81] text-white flex items-center justify-center font-bold text-base tracking-wider shrink-0 shadow-xs">
                    {getInitials(activeLead.company_name)}
                  </div>

                  <div className="flex flex-col">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-zinc-100 tracking-tight">
                        {activeLead.company_name}
                      </h2>
                      
                      {/* New Lead Pill Badge */}
                      <span className="px-2.5 py-0.5 rounded-full bg-[#0F172A] text-white text-[11px] font-semibold">
                        New lead
                      </span>

                      {/* Domain External Link */}
                      <a
                        href={displayUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-mono text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white inline-flex items-center gap-1 transition"
                      >
                        <LinkIcon size={12} className="text-amber-600" />
                        <span>{activeLead.domain}</span>
                        <ExternalLink size={11} />
                      </a>
                    </div>
                  </div>
                </div>

                {/* Metadata Pills Row (Exact Wireframe Match) */}
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <div className="px-3.5 py-1.5 rounded-full border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/80 text-slate-700 dark:text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                    <MapPin size={13} className="text-slate-400" />
                    <span>{activeLead.location_mentioned || 'USA / North America'}</span>
                  </div>

                  <div className="px-3.5 py-1.5 rounded-full border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/80 text-slate-700 dark:text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                    <Briefcase size={13} className="text-slate-400" />
                    <span>{activeLead.industry || 'Software Development'}</span>
                  </div>

                  <div className="px-3.5 py-1.5 rounded-full border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/80 text-slate-700 dark:text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                    <Users size={13} className="text-slate-400" />
                    <span>{activeLead.employee_count ? `${activeLead.employee_count} emp` : '19 emp'}</span>
                  </div>

                  <div className="px-3.5 py-1.5 rounded-full border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/80 text-slate-700 dark:text-zinc-200 font-medium flex items-center gap-1.5 shadow-2xs">
                    <Calendar size={13} className="text-slate-400" />
                    <span>{activeLead.funding_stage && activeLead.funding_stage !== 'UNKNOWN' ? activeLead.funding_stage : 'Venture Backed'}</span>
                  </div>
                </div>
              </div>

              {/* Sub-Tab Navigation Bar (Exact Wireframe Match) */}
              <div className="px-5 sm:px-6 py-2.5 bg-white dark:bg-[#12121a] border-b border-slate-200/80 dark:border-zinc-800 flex items-center gap-2 overflow-x-auto shrink-0 text-xs font-bold">
                {/* Tab 1: Signals */}
                <button
                  type="button"
                  onClick={() => setActiveDetailTab('signals')}
                  className={`px-3.5 py-1.5 rounded-xl flex items-center gap-1.5 transition ${
                    activeDetailTab === 'signals'
                      ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 shadow-2xs border border-slate-200 dark:border-zinc-700'
                      : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <Signal size={14} />
                  <span>Signals</span>
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-[#1E1B4B] text-indigo-200 font-mono">
                    {signalsCount}
                  </span>
                </button>

                {/* Tab 2: Company Insights */}
                <button
                  type="button"
                  onClick={() => setActiveDetailTab('insights')}
                  className={`px-3.5 py-1.5 rounded-xl flex items-center gap-1.5 transition ${
                    activeDetailTab === 'insights'
                      ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 shadow-2xs border border-slate-200 dark:border-zinc-700'
                      : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <LineChart size={14} />
                  <span>Company Insights</span>
                </button>

                {/* Tab 3: Jobs */}
                <button
                  type="button"
                  onClick={() => setActiveDetailTab('jobs')}
                  className={`px-3.5 py-1.5 rounded-xl flex items-center gap-1.5 transition ${
                    activeDetailTab === 'jobs'
                      ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 shadow-2xs border border-slate-200 dark:border-zinc-700'
                      : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <Briefcase size={14} />
                  <span>Jobs</span>
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-[#064E3B] text-emerald-200 font-mono">
                    {jobsCount}
                  </span>
                </button>

                {/* Tab 4: Decision Makers */}
                <button
                  type="button"
                  onClick={() => setActiveDetailTab('people')}
                  className={`px-3.5 py-1.5 rounded-xl flex items-center gap-1.5 transition ${
                    activeDetailTab === 'people'
                      ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 shadow-2xs border border-slate-200 dark:border-zinc-700'
                      : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  <Users size={14} />
                  <span>Decision Makers</span>
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-[#3B0764] text-purple-200 font-mono">
                    {contactsCount}
                  </span>
                </button>
              </div>

              {/* Tab Content Body (Scrollable) */}
              <div className="flex-1 min-h-0 overflow-y-auto p-5 sm:p-6 space-y-6">
                
                {/* ===== TAB 1: SIGNALS (EXACT WIREFRAME MATCH) ===== */}
                {activeDetailTab === 'signals' && (
                  <div className="space-y-6 animate-fade-in font-sans">
                    
                    {/* HERO FIT CARD: Mint Green background as in wireframe */}
                    <div className="p-6 sm:p-7 rounded-2xl bg-[#F2FBF6] dark:bg-emerald-950/20 border border-[#D1F3E0] dark:border-emerald-900/40 shadow-xs flex flex-col sm:flex-row items-center gap-6 sm:gap-8 text-left">
                      
                      {/* Left Score Column */}
                      <div className="flex flex-col items-center justify-center shrink-0 min-w-[95px] text-center">
                        <div className="text-4xl sm:text-5xl font-black font-sans text-emerald-600 dark:text-emerald-400 leading-none tracking-tight">
                          {displayScore}
                        </div>
                        <div className="text-xs font-semibold text-slate-400 dark:text-zinc-500 mt-1.5 font-mono">
                          / 100
                        </div>
                        <div className="mt-2.5">
                          <span className={`inline-block px-3 py-0.5 rounded-full text-[11px] font-bold ${
                            displayScore >= 70
                              ? 'bg-[#D1F3E0] text-emerald-700 dark:bg-emerald-950/80 dark:text-emerald-300'
                              : displayScore >= 40
                              ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                              : 'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-300'
                          }`}>
                            {activeLead?.intent_classification || (displayScore >= 70 ? 'Hot' : displayScore >= 40 ? 'Warm' : 'Watching')}
                          </span>
                        </div>
                      </div>

                      {/* Right Fit Reasoning */}
                      <div className="flex-1 space-y-1.5 text-left">
                        <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-zinc-100 tracking-tight">
                          {activeLead?.icp_fit ? `${activeLead.icp_fit} fit` : (displayScore >= 70 ? 'Strong fit' : displayScore >= 40 ? 'Moderate fit' : 'Low fit')}
                        </h3>
                        <p className="text-xs sm:text-[13px] text-slate-600 dark:text-zinc-300 leading-relaxed font-normal">
                          {activeLead?.why_now || activeLead?.one_line_reason || activeLead?.ai_verdict || "The company's recent expansion indicates a strong need for talent acquisition and growth support."}
                        </p>
                      </div>
                    </div>

                    {/* SIGNAL TIMELINE CARD (Exact Wireframe Match) */}
                    <div className="p-6 sm:p-7 rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs space-y-5">
                      <div className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500">
                        SIGNAL TIMELINE
                      </div>

                      <div className="space-y-4">
                        {(!activeLead.signals || activeLead.signals.length === 0) ? (
                          <div className="text-center py-6 text-xs text-slate-400 dark:text-zinc-500">
                            No verified signals detected for this company yet.
                          </div>
                        ) : (
                          activeLead.signals.map((sig, idx) => {
                            let label = (sig.recency_label || '').trim();
                            if (!label && sig.event_date) {
                              const d = new Date(sig.event_date);
                              if (!isNaN(d.getTime())) {
                                const days = Math.max(0, Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24)));
                                if (days <= 30) label = '< 1 month';
                                else if (days <= 90) label = '1-3 months';
                                else if (days <= 180) label = '3-6 months';
                                else if (days <= 365) label = '6-12 months';
                                else label = '> 1 yr';
                              }
                            }
                            if (!label) label = '< 1 month';

                            return (
                              <div
                                key={idx}
                                className="flex items-start justify-between gap-4 pb-4 border-b border-slate-100 dark:border-zinc-800/80 last:border-b-0 last:pb-0"
                              >
                                <div className="flex items-start gap-3.5 min-w-0">
                                  {/* Blue Square Box Icon matching image */}
                                  <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400 flex items-center justify-center shrink-0 border border-blue-200 dark:border-blue-800 mt-0.5">
                                    <div className="w-3.5 h-3.5 border-2 border-blue-600 dark:border-blue-400 rounded-xs" />
                                  </div>

                                  {/* Title, Verbatim Quote, Source Link */}
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

                                {/* Recency Badge */}
                                <div className="shrink-0 pt-0.5">
                                  <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                    {label}
                                  </span>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>

                  </div>
                )}

                {/* ===== TAB 2: COMPANY INSIGHTS ===== */}
                {activeDetailTab === 'insights' && (
                  <div className="animate-fade-in">
                    <JobsTab lead={activeLead} defaultTab="insights" />
                  </div>
                )}

                {/* ===== TAB 3: JOBS ===== */}
                {activeDetailTab === 'jobs' && (
                  <div className="animate-fade-in">
                    <JobsTab lead={activeLead} defaultTab="jobs" />
                  </div>
                )}

                {/* ===== TAB 4: DECISION MAKERS ===== */}
                {activeDetailTab === 'people' && (
                  <div className="space-y-4 animate-fade-in">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                        <Users size={16} className="text-emerald-500" /> Key Executive Decision Makers
                      </h3>
                      <span className="text-xs text-slate-500 font-mono">
                        {contactsCount} contacts found
                      </span>
                    </div>

                    {(!activeLead.contacts || activeLead.contacts.length === 0) ? (
                      <div className="p-8 text-center rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs text-slate-400">
                        No executive decision makers extracted for this company yet.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {activeLead.contacts.map((contact, idx) => {
                          const cName = cleanName(contact.name);
                          const cInitial = cName.charAt(0).toUpperCase();
                          return (
                            <div
                              key={idx}
                              className="p-4 rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xs flex items-start justify-between gap-3"
                            >
                              <div className="flex items-start gap-3 min-w-0">
                                <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 font-bold text-sm flex items-center justify-center shrink-0 border border-slate-200 dark:border-zinc-700">
                                  {cInitial}
                                </div>
                                <div className="space-y-0.5 min-w-0">
                                  <h4 className="text-sm font-bold text-slate-900 dark:text-zinc-100 truncate">
                                    {cName}
                                  </h4>
                                  <p className="text-xs text-slate-500 dark:text-zinc-400 truncate">
                                    {contact.title || 'Executive Leadership'}
                                  </p>
                                  {contact.department && (
                                    <span className="inline-block px-2 py-0.5 rounded-md bg-slate-100 dark:bg-zinc-800 text-[10px] font-medium text-slate-600 dark:text-zinc-300 mt-1">
                                      {contact.department}
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div className="flex items-center gap-1 shrink-0">
                                {contact.email && (
                                  <a
                                    href={`mailto:${contact.email}`}
                                    className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:text-emerald-600 hover:border-emerald-300 transition"
                                    title={`Email ${cName}`}
                                  >
                                    <Mail size={13} />
                                  </a>
                                )}
                                {contact.linkedin_url && (
                                  <a
                                    href={contact.linkedin_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:text-blue-600 hover:border-blue-300 transition"
                                    title="LinkedIn Profile"
                                  >
                                    <Linkedin size={13} />
                                  </a>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

              </div>
            </>
          ) : (
            <div className="p-12 text-center text-sm text-slate-400 dark:text-zinc-500">
              Select a company from the left panel to inspect detailed intent intelligence.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
