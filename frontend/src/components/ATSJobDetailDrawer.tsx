import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  ExternalLink,
  MapPin,
  Building2,
  DollarSign,
  Briefcase,
  CheckCircle2,
  Layers,
  Globe,
  FileText,
  Mail,
  Users,
  UserCheck,
  Loader2,
  Search,
  Linkedin,
  RefreshCw
} from 'lucide-react';

export interface DecisionMakerItem {
  name: string;
  title: string;
  email: string;
  phone?: string;
  linkedin_url?: string;
  status?: 'DELIVERABLE' | 'HIGH_PROBABILITY' | 'CATCH_ALL' | 'INVALID' | string;
}

export interface ATSJobCardData {
  id: string;
  run_id?: string;
  title: string;
  normalized_title?: string;
  company_name: string;
  company_website?: string;
  company_logo?: string;
  location?: string;
  workplace_type?: string;
  employment_type?: string;
  experience_level?: string;
  compensation_min?: number;
  compensation_max?: number;
  compensation_currency?: string;
  compensation_period?: string;
  ats_source?: string;
  apply_url?: string;
  listing_url?: string;
  description?: string;
  summary?: string;
  qualifications?: {
    must_have?: {
      education?: string[];
      certifications?: string[];
      skills?: Array<{ name: string; type: string }>;
    };
    preferred?: {
      education?: string[];
      certifications?: string[];
      skills?: Array<{ name: string; type: string }>;
    };
  };
  responsibilities?: string[];
  benefits?: string[];
  date_posted?: string;
  created_at?: string;
  verified_contact?: DecisionMakerItem;
  verified_contacts?: DecisionMakerItem[];
  contacts_enriched_at?: string;
}

interface ATSJobDetailDrawerProps {
  job: ATSJobCardData | null;
  isOpen: boolean;
  onClose: () => void;
  generalSummary?: string;
  isEnriching?: boolean;
  onTriggerEnrich?: (forceRefresh?: boolean) => void;
}

export default function ATSJobDetailDrawer({
  job,
  isOpen,
  onClose,
  isEnriching = false,
  onTriggerEnrich
}: ATSJobDetailDrawerProps) {
  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<'job' | 'decision_makers'>('job');

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isEnriching) {
      setActiveTab('decision_makers');
    }
  }, [isEnriching]);

  if (!mounted || typeof document === 'undefined') {
    return null;
  }

  const mustHaveSkills = job?.qualifications?.must_have?.skills || [];
  const responsibilities = job?.responsibilities || [];

  const formattedSalary =
    job?.compensation_min && job?.compensation_max
      ? `$${job.compensation_min.toLocaleString()} - $${job.compensation_max.toLocaleString()} ${job.compensation_currency || 'USD'}`
      : job?.compensation_min
      ? `$${job.compensation_min.toLocaleString()}+ ${job.compensation_currency || 'USD'}`
      : 'Compensation Not Specified';

  // Build decision makers list
  const decisionMakers: DecisionMakerItem[] = [];
  if (job?.verified_contacts && job.verified_contacts.length > 0) {
    decisionMakers.push(...job.verified_contacts);
  } else if (job?.verified_contact?.email) {
    decisionMakers.push(job.verified_contact);
  }

  const hasVerifiedContacts = decisionMakers.length > 0;

  // Check freshness date (30-day lifecycle)
  let isStale = false;
  let enrichedDateLabel = 'Verified';
  if (job?.contacts_enriched_at) {
    try {
      const enrichDate = new Date(job.contacts_enriched_at);
      if (!isNaN(enrichDate.getTime())) {
        const daysOld = Math.floor((Date.now() - enrichDate.getTime()) / (1000 * 60 * 60 * 24));
        isStale = daysOld >= 30;
        enrichedDateLabel = daysOld === 0
          ? 'Verified today'
          : daysOld === 1
          ? 'Verified yesterday'
          : `Verified ${daysOld} days ago`;
      }
    } catch {
      enrichedDateLabel = 'Verified';
    }
  }

  const cleanSummary = (job?.summary || '').split('[Contact]')[0].trim();

  // FullEnrich Email Status Formatter matching reference image
  const renderVerificationStatus = (status?: string) => {
    const s = (status || 'DELIVERABLE').toUpperCase();
    if (s.includes('HIGH') || s.includes('PROBABILITY')) {
      return (
        <span className="text-[11px] font-bold text-amber-500 dark:text-amber-400">
          High probability
        </span>
      );
    }
    if (s.includes('CATCH')) {
      return (
        <span className="text-[11px] font-bold text-orange-500 dark:text-orange-400">
          Catch-all
        </span>
      );
    }
    if (s.includes('INVALID')) {
      return (
        <span className="text-[11px] font-bold text-rose-500 dark:text-rose-400">
          Invalid
        </span>
      );
    }
    return (
      <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
        Deliverable
      </span>
    );
  };

  return createPortal(
    <AnimatePresence mode="wait">
      {isOpen && job && (
        <div className="fixed inset-0 z-[99999] overflow-hidden">
          {/* Backdrop */}
          <motion.div
            key="drawer-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-950/60 dark:bg-black/80 backdrop-blur-xs z-[99999]"
          />

          {/* Slide-over Drawer Panel */}
          <motion.aside
            key="drawer-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 220 }}
            className="fixed right-0 top-0 bottom-0 w-full md:w-[45%] sm:min-w-[440px] max-w-full bg-white dark:bg-[#111118] border-l border-slate-200 dark:border-zinc-800 shadow-2xl z-[100000] flex flex-col font-sans overflow-x-hidden"
          >
            {/* 1. DRAWER TOP HEADER */}
            <div className="px-6 py-5 border-b border-slate-200 dark:border-zinc-800/80 bg-slate-50/50 dark:bg-zinc-900/40 flex items-start justify-between gap-4 shrink-0">
              <div className="flex items-start gap-3.5">
                <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 dark:bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-0.5">
                  {job.company_logo ? (
                    <img
                      src={job.company_logo}
                      alt={job.company_name}
                      className="w-8 h-8 object-contain rounded-lg"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                  ) : (
                    <Building2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold font-mono uppercase tracking-wider text-slate-500 dark:text-zinc-400">
                      {job.company_name}
                    </span>
                    {job.company_website && (
                      <a
                        href={job.company_website.startsWith('http') ? job.company_website : `https://${job.company_website}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline inline-flex items-center gap-0.5 font-medium"
                      >
                        <Globe size={11} /> Website
                      </a>
                    )}
                  </div>
                  <h2 className="text-lg sm:text-xl font-black text-slate-900 dark:text-zinc-100 tracking-tight leading-snug mt-0.5">
                    {job.title}
                  </h2>
                </div>
              </div>

              <button
                onClick={onClose}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-200/50 dark:hover:bg-zinc-800 transition cursor-pointer"
                aria-label="Close drawer"
              >
                <X size={20} />
              </button>
            </div>

            {/* 2. TAB NAVIGATION SWITCHER */}
            <div className="px-6 py-2.5 bg-white dark:bg-[#111118] border-b border-slate-200/80 dark:border-zinc-800 flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setActiveTab('job')}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer ${
                  activeTab === 'job'
                    ? 'bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 shadow-2xs border border-slate-200 dark:border-zinc-700'
                    : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Briefcase size={14} />
                <span>Job Details</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('decision_makers')}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer ${
                  activeTab === 'decision_makers'
                    ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 shadow-2xs border border-emerald-300 dark:border-emerald-700/60'
                    : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Users size={14} />
                <span>Decision Makers</span>
                {hasVerifiedContacts ? (
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                ) : isEnriching ? (
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                ) : null}
              </button>
            </div>

            {/* 3. SCROLLABLE CONTENT */}
            <div className="flex-1 overflow-y-auto px-6 py-6">

              {/* ============================================================ */}
              {/* TAB 1: JOB DETAILS SECTION                                   */}
              {/* ============================================================ */}
              {activeTab === 'job' && (
                <div className="space-y-6 animate-fade-in">
                  {/* Badges */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-2.5 py-1 rounded-xl text-xs font-bold font-mono border bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                      {job.ats_source?.toUpperCase() || 'ATS'}
                    </span>
                    <span className="px-2.5 py-1 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700">
                      {job.workplace_type || 'Remote'}
                    </span>
                    <span className="px-2.5 py-1 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700">
                      {job.employment_type || 'Full-time'}
                    </span>
                    {job.experience_level && (
                      <span className="px-2.5 py-1 rounded-xl text-xs font-semibold bg-emerald-100/60 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-300">
                        {job.experience_level}
                      </span>
                    )}
                  </div>

                  {/* Highlights */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-4 rounded-2xl bg-slate-50 dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800 flex items-start gap-3">
                      <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                        <DollarSign size={18} />
                      </div>
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500 font-mono">
                          Compensation
                        </span>
                        <p className="text-sm font-bold text-slate-900 dark:text-zinc-100 mt-0.5">
                          {formattedSalary}
                        </p>
                      </div>
                    </div>

                    <div className="p-4 rounded-2xl bg-slate-50 dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800 flex items-start gap-3">
                      <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-600 dark:text-teal-400 shrink-0">
                        <MapPin size={18} />
                      </div>
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500 font-mono">
                          Location
                        </span>
                        <p className="text-sm font-bold text-slate-900 dark:text-zinc-100 mt-0.5 truncate max-w-[180px]">
                          {job.location || 'United States'}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Executive Summary */}
                  {cleanSummary && (
                    <div className="space-y-2">
                      <h3 className="text-xs font-extrabold uppercase tracking-wider font-mono text-slate-500 dark:text-zinc-400 flex items-center gap-1.5">
                        <FileText size={14} /> Executive Summary
                      </h3>
                      <p className="text-sm text-slate-700 dark:text-zinc-300 leading-relaxed bg-slate-50/50 dark:bg-zinc-900/30 p-4 rounded-2xl border border-slate-200/60 dark:border-zinc-800/60">
                        {cleanSummary}
                      </p>
                    </div>
                  )}

                  {/* Must-Have Qualifications */}
                  {mustHaveSkills.length > 0 && (
                    <div className="space-y-2.5">
                      <h3 className="text-xs font-extrabold uppercase tracking-wider font-mono text-slate-500 dark:text-zinc-400 flex items-center gap-1.5">
                        <CheckCircle2 size={14} className="text-emerald-500" /> Must-Have Qualifications
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {mustHaveSkills.map((sk, idx) => (
                          <span
                            key={idx}
                            className="px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/50"
                          >
                            {sk.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Responsibilities */}
                  {responsibilities.length > 0 && (
                    <div className="space-y-2.5">
                      <h3 className="text-xs font-extrabold uppercase tracking-wider font-mono text-slate-500 dark:text-zinc-400 flex items-center gap-1.5">
                        <Layers size={14} /> Key Responsibilities
                      </h3>
                      <ul className="space-y-2 text-sm text-slate-700 dark:text-zinc-300">
                        {responsibilities.map((resp, idx) => (
                          <li key={idx} className="flex items-start gap-2.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 shrink-0" />
                            <span className="leading-relaxed">{resp}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* ============================================================ */}
              {/* TAB 2: DECISION MAKERS SECTION (EXACT REFERENCE SCREENSHOT)  */}
              {/* ============================================================ */}
              {activeTab === 'decision_makers' && (
                <div className="space-y-6 animate-fade-in">
                  
                  {/* STATE 1: CONTACTS FOUND & RENDERED (EXACT MATCH TO REFERENCE) */}
                  {hasVerifiedContacts ? (
                    <div className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-[#181824] border border-slate-200 dark:border-zinc-800 shadow-sm space-y-4">
                      
                      {/* Freshness Status Bar & Re-verify Action */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100 dark:border-zinc-800/80">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50">
                            <CheckCircle2 size={12} />
                            {enrichedDateLabel}
                          </span>
                          {isStale ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400 border border-amber-200 dark:border-amber-800/50">
                              30+ days old (Needs re-verification)
                            </span>
                          ) : (
                            <span className="text-[11px] text-slate-400 dark:text-zinc-500 font-medium">
                              (Stored in DB · 0 credits consumed)
                            </span>
                          )}
                        </div>

                        {onTriggerEnrich && (
                          <button
                            type="button"
                            onClick={() => onTriggerEnrich(true)}
                            disabled={isEnriching}
                            className={`text-xs font-semibold px-2.5 py-1 rounded-lg transition inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
                              isStale
                                ? 'bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 hover:bg-amber-200 border border-amber-300 dark:border-amber-700/60 font-bold'
                                : 'text-slate-500 dark:text-zinc-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-slate-100 dark:hover:bg-zinc-800'
                            }`}
                            title="Force refresh contacts from FullEnrich"
                          >
                            <RefreshCw size={12} className={isEnriching ? "animate-spin" : ""} />
                            <span>{isStale ? "Re-verify Decision Maker" : "Re-verify"}</span>
                          </button>
                        )}
                      </div>

                      {/* Decision Maker Rows */}
                      <div className="divide-y divide-slate-100 dark:divide-zinc-800/80">
                        {decisionMakers.map((contact, idx) => (
                          <div
                            key={idx}
                            className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 first:pt-1 last:pb-2"
                          >
                            {/* Left: Person Name & Title */}
                            <div className="space-y-0.5">
                              <h4 className="text-sm font-black text-slate-900 dark:text-zinc-100 tracking-tight">
                                {contact.name}
                              </h4>
                              <p className="text-xs font-medium text-slate-500 dark:text-zinc-400">
                                {contact.title || 'Talent Acquisition Lead'}
                              </p>
                            </div>

                            {/* Right: Email & FullEnrich Verification Status */}
                            <div className="text-left sm:text-right space-y-0.5">
                              <div>
                                <a
                                  href={`mailto:${contact.email}`}
                                  className="text-xs font-mono font-bold text-sky-600 dark:text-sky-400 hover:underline inline-flex items-center gap-1"
                                >
                                  {contact.email}
                                </a>
                              </div>
                              <div>
                                {renderVerificationStatus(contact.status)}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Bottom Bounce Rate Legend (Exact match to reference image) */}
                      <div className="pt-4 border-t border-slate-100 dark:border-zinc-800/80 space-y-1.5 text-xs text-slate-500 dark:text-zinc-400 font-medium">
                        <div className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                          <span>
                            <strong className="text-slate-700 dark:text-zinc-300 font-bold">Deliverable</strong> — verified, ~2% bounce rate
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                          <span>
                            <strong className="text-slate-700 dark:text-zinc-300 font-bold">High probability</strong> — catch-all, likely valid, ~9% bounce rate
                          </span>
                        </div>
                      </div>

                    </div>
                  ) : isEnriching ? (
                    /* STATE 2: ACTIVE RESOLUTION IN PROGRESS */
                    <div className="p-6 rounded-2xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/60 space-y-3 text-center">
                      <Loader2 size={24} className="animate-spin text-blue-600 dark:text-blue-400 mx-auto" />
                      <div className="space-y-1">
                        <h4 className="text-sm font-bold text-blue-950 dark:text-blue-200">
                          Resolving Decision-Maker Intelligence
                        </h4>
                        <p className="text-xs text-blue-700 dark:text-blue-300/90 leading-relaxed max-w-sm mx-auto">
                          Finding the hiring manager and performing triple-verification deliverability checks (~15–30s)...
                        </p>
                      </div>
                    </div>
                  ) : (
                    /* STATE 3: NOT YET ENRICHED */
                    <div className="p-8 rounded-2xl border border-dashed border-slate-200 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/30 text-center space-y-4">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-zinc-800 text-slate-400 dark:text-zinc-500 flex items-center justify-center mx-auto">
                        <Users size={22} />
                      </div>
                      <div className="space-y-1 max-w-xs mx-auto">
                        <h4 className="text-sm font-bold text-slate-800 dark:text-zinc-200">
                          No Decision Maker Loaded Yet
                        </h4>
                        <p className="text-xs text-slate-500 dark:text-zinc-400 leading-relaxed">
                          Decision makers are not preloaded to conserve agency API quotas. Click below to resolve this company's hiring lead.
                        </p>
                      </div>

                      {onTriggerEnrich && (
                        <button
                          type="button"
                          onClick={() => onTriggerEnrich(false)}
                          className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md shadow-emerald-600/20 transition inline-flex items-center gap-2 cursor-pointer"
                        >
                          <Search size={14} />
                          <span>Find Decision Maker</span>
                        </button>
                      )}
                    </div>
                  )}

                </div>
              )}

            </div>

            {/* 4. FOOTER */}
            <div className="p-5 border-t border-slate-200 dark:border-zinc-800/80 bg-slate-50/80 dark:bg-zinc-900/60 flex items-center justify-between gap-4 shrink-0">
              <div className="text-xs text-slate-500 dark:text-zinc-400 font-mono">
                Source: <span className="font-bold text-slate-700 dark:text-zinc-300">{job.ats_source?.toUpperCase() || 'ATS'}</span>
              </div>

              {job.apply_url || job.listing_url ? (
                <a
                  href={job.apply_url || job.listing_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-6 py-2.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-sm shadow-md transition flex items-center gap-2 group"
                >
                  Link
                  <ExternalLink size={16} className="group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                </a>
              ) : null}
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}