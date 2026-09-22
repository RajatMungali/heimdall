import { useEffect, useMemo, useState } from 'react';
import { motion, Variants } from 'framer-motion';
import { Sparkles, LayoutGrid, Bookmark, Settings as SettingsIcon } from 'lucide-react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import LeadTable from './components/LeadTable';
import ConfidenceGauge from './components/ConfidenceGauge';
import SignalAnalytics from './components/SignalAnalytics';
import TrendPanel from './components/TrendPanel';
import Settings from './components/Settings';
import SocialPostsView from './components/SocialPostsView';
import SignalDistribution from './components/SignalDistribution';
import DocumentMagnifierScan from './components/DocumentMagnifierScan';
import TrackedLeadsView from './components/TrackedLeadsView';
import ATSJobsView from './components/ATSJobsView';
import { fetchLeads, fetchPipelineStatus } from './lib/api';
import type { LeadDetailResponse } from './types/lead';

const BriefcaseIcon = ({ size = 20, className = "" }: { size?: number; className?: string }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="M8 6V4.2C8 3 9 2 10.2 2h3.6C15 2 16 3 16 4.2V6" />
    <rect x="2.5" y="6" width="19" height="15" rx="3.5" />
    <path d="M2.5 12.5C6 14.8 9.5 15.2 12 15.2C14.5 15.2 18 14.8 21.5 12.5" />
    <circle cx="12" cy="14.8" r="1.8" fill="currentColor" stroke="currentColor" strokeWidth="0.4" />
  </svg>
);

export default function App() {
  const [leads, setLeads] = useState<LeadDetailResponse[]>([]);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [isDark, setIsDark] = useState(false);
  const [currentView, setCurrentView] = useState('dashboard');
  const [globalSearchTerm, setGlobalSearchTerm] = useState('');
  const [scannedLeads, setScannedLeads] = useState<LeadDetailResponse[]>([]);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [trackedLeadIds, setTrackedLeadIds] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('tracked_lead_ids');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const mobileNavItems = [
    { label: 'Dashboard', key: 'dashboard', icon: LayoutGrid },
    { label: 'Track Jobs', key: 'ats_jobs', icon: BriefcaseIcon },
    { label: 'Saved Leads', key: 'statistics', icon: Bookmark },
    { label: 'Settings', key: 'settings', icon: SettingsIcon },
  ];

  const handleToggleTrackLead = (leadId: string) => {
    setTrackedLeadIds((prev) => {
      const next = prev.includes(leadId)
        ? prev.filter((id) => id !== leadId)
        : [...prev, leadId];
      localStorage.setItem('tracked_lead_ids', JSON.stringify(next));
      return next;
    });
  };

  const savedLeads = useMemo(() => {
    let list = [];
    if (trackedLeadIds.length === 0) {
      list = leads.filter((l) => {
        const score = l.icp_score ?? l.intent_score ?? 0;
        return l.badge === 'new_today' || score > 75;
      });
    } else {
      list = leads.filter((l) => {
        const key = String(l.id || l.domain || l.company_name);
        return (
          trackedLeadIds.includes(key) ||
          trackedLeadIds.includes(l.id) ||
          trackedLeadIds.includes(l.domain) ||
          trackedLeadIds.includes(l.company_name)
        );
      });
    }

    return list.sort((a, b) => {
      const scoreA = a.icp_score ?? a.intent_score ?? 0;
      const scoreB = b.icp_score ?? b.intent_score ?? 0;
      return scoreB - scoreA;
    });
  }, [leads, trackedLeadIds]);

  // Clear temporary pipeline results state when user switches tabs from sidebar
  useEffect(() => {
    setScannedLeads([]);
  }, [currentView]);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light-theme');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light-theme');
    }
  }, [isDark]);

  // Continuous backend health check & auto-reconnect polling
  useEffect(() => {
    let isMounted = true;

    const checkBackend = async () => {
      try {
        const apiLeads = await fetchLeads();
        if (isMounted) {
          setLeads(apiLeads);
          setStatus('success');
        }
      } catch (err) {
        if (isMounted) {
          setStatus('error');
        }
      }
    };

    // Initial fetch on mount
    checkBackend();

    const pollInterval = status === 'error' ? 3000 : 10 * 1000;
    const interval = setInterval(checkBackend, pollInterval);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [status]);

  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);

  // Compute KPI values
  const totalScans = leads.length;

  const strongICPCount = useMemo(() => {
    return leads.filter((l) => {
      const score = l.icp_score ?? l.intent_score ?? 0;
      return score >= 50; // Strong (>75) or Partial (50-75)
    }).length;
  }, [leads]);

  const globalAvgConfidence = useMemo(() => {
    if (leads.length === 0) return 0;
    const sum = leads.reduce((acc, l) => acc + l.confidence.verified, 0);
    return Math.round(sum / leads.length);
  }, [leads]);

  const selectedLead = useMemo(() => {
    return leads.find((l) => l.id === selectedLeadId) || null;
  }, [leads, selectedLeadId]);

  const researchHoursSaved = useMemo(() => {
    const companiesScored = leads.length;
    return Math.round((companiesScored * 25) / 60);
  }, [leads]);

  const newTodayCount = useMemo(() => {
    const todayStr = new Date().toISOString().split('T')[0];
    return leads.filter((l) => {
      if (!l.last_updated) return l.badge === 'new_today';
      const leadDateStr = new Date(l.last_updated).toISOString().split('T')[0];
      return (l.badge === 'new_today' || leadDateStr === todayStr) && leadDateStr === todayStr;
    }).length;
  }, [leads]);

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.1,
      }
    }
  };

  const itemVariants: Variants = {
    hidden: { y: 20, opacity: 0, scale: 0.95 },
    show: { y: 0, opacity: 1, scale: 1, transition: { type: 'spring', stiffness: 200, damping: 20 } }
  };

  return (
    <>
      <div className="relative flex flex-col h-screen h-[100dvh] bg-nexa-bg overflow-hidden">
      {/* Golden Light Flare */}
      <div className="nexa-flare" />

      {/* ===== Main Dashboard Layout ===== */}
      <div className="relative z-10 flex flex-1 h-full gap-2.5 sm:gap-3 lg:gap-1.5 pl-1 pr-0.5 sm:pr-2.5 pt-1 pb-1 sm:px-2.5 lg:px-2.5 lg:pt-2.5 lg:pb-2.5 overflow-hidden">
        {/* Left Column: Sidebar Navigation (Desktop + Mobile Drawer) */}
        <Sidebar
          currentView={currentView}
          setCurrentView={setCurrentView}
          isDark={isDark}
          setIsDark={setIsDark}
          status={status}
          isMobileOpen={isMobileSidebarOpen}
          setIsMobileOpen={setIsMobileSidebarOpen}
        />

        {/* Main Workspace */}
        <main className="flex min-w-0 flex-1 flex-col gap-2.5 pl-1 pr-1 sm:pr-1.5 lg:pl-1 pt-0 pb-11 lg:pb-1 overflow-y-auto overflow-x-hidden">
          {/* Top Header Bar */}
          <Header
            status={status}
            searchTerm={globalSearchTerm}
            setSearchTerm={setGlobalSearchTerm}
            isDark={isDark}
            setIsDark={setIsDark}
            onToggleMobileSidebar={() => setIsMobileSidebarOpen((prev) => !prev)}
          />

          {currentView === 'settings' ? (
            <Settings />
          ) : currentView === 'social media posts' ? (
            <SocialPostsView />
          ) : currentView === 'ats_jobs' ? (
            <ATSJobsView />
          ) : currentView === 'pipeline' ? (
            <div className="flex flex-col flex-1 min-h-0">
              <LeadTable
                leads={leads}
                scannedLeads={scannedLeads}
                setScannedLeads={setScannedLeads}
                selectedLeadId={selectedLeadId}
                onSelectLead={setSelectedLeadId}
                onLeadIngested={(newLead) =>
                  setLeads((prev) => {
                    const key = String(newLead.id || newLead.domain || newLead.company_name);
                    const exists = prev.some(
                      (l) => String(l.id || l.domain || l.company_name) === key
                    );
                    if (exists) {
                      return prev.map((l) =>
                        String(l.id || l.domain || l.company_name) === key ? newLead : l
                      );
                    }
                    return [newLead, ...prev];
                  })
                }
                onLeadDeleted={(id) => {
                  if (selectedLeadId === id) setSelectedLeadId(null);
                  setLeads(leads.filter((l) => l.id !== id));
                }}
                status={status}
                externalSearchTerm={globalSearchTerm}
                isPipelineTab={true}
                trackedLeadIds={trackedLeadIds}
                onToggleTrackLead={handleToggleTrackLead}
              />
            </div>
          ) : currentView === 'statistics' ? (
            <div className="flex flex-col flex-1 min-h-0">
              <TrackedLeadsView
                leads={savedLeads}
                selectedLeadId={selectedLeadId}
                onSelectLead={setSelectedLeadId}
                onToggleTrackLead={handleToggleTrackLead}
                onLeadDeleted={(id) => {
                  if (selectedLeadId === id) setSelectedLeadId(null);
                  setLeads(leads.filter((l) => l.id !== id));
                }}
              />
            </div>
          ) : (
            <>
              {/* Default Main Dashboard Hero Banner */}
              <div className="flex items-center gap-2.5 sm:gap-3 px-1 pb-1">
                <div className="flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-500/15 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/30 shadow-xs">
                  <Sparkles size={16} className="stroke-[2.5px]" />
                </div>
                <div>
                  <h2 className="text-sm sm:text-lg font-bold text-slate-900 dark:text-zinc-100 tracking-tight">
                    Lead Intelligence Signals
                  </h2>
                  <p className="text-[11px] sm:text-xs text-slate-600 dark:text-zinc-400 mt-0.5 font-medium">
                    Discover active intent signals and monitor target companies
                  </p>
                </div>
              </div>

              {/* ===== KPI Ribbon row ===== */}
              <motion.div
                className="grid grid-cols-2 gap-1.5 sm:gap-4 lg:grid-cols-4 w-full flex-shrink-0"
                variants={containerVariants}
                initial="hidden"
                animate="show"
              >
                  {/* Card 1: Total automated sweeps/scans processed */}
                  <motion.div variants={itemVariants} className="nexa-card px-2.5 py-1.5 sm:p-4 flex flex-col justify-between min-h-[3.1rem] sm:h-24 relative overflow-hidden">
                    <span className="text-[8px] sm:text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                      Automated Sweeps
                    </span>
                    <div className="flex items-baseline gap-1 sm:gap-2 mt-0.5 sm:mt-1">
                      <span className="text-sm sm:text-3xl font-extrabold text-zinc-100">
                        {totalScans}
                      </span>
                      <span className="text-[7.5px] sm:text-xs text-emerald-400 font-mono truncate">
                        ● Active
                      </span>
                    </div>
                  </motion.div>

                  {/* Card 2: Strong ICP matches found */}
                  <motion.div variants={itemVariants} className="nexa-card px-2.5 py-1.5 sm:p-4 flex flex-col justify-between min-h-[3.1rem] sm:h-24 relative overflow-hidden">
                    <span className="text-[8px] sm:text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                      Qualified Leads
                    </span>
                    <div className="flex items-baseline gap-1 sm:gap-2 mt-0.5 sm:mt-1">
                      <span className="text-sm sm:text-3xl font-extrabold text-zinc-100">
                        {strongICPCount}
                      </span>
                      <span className="text-[7.5px] sm:text-xs text-zinc-500 font-mono truncate">
                        Match verified
                      </span>
                    </div>
                  </motion.div>

                  {/* Card 3: NEW TODAY */}
                  <motion.div variants={itemVariants} className="nexa-card px-2.5 py-1.5 sm:p-4 flex flex-col justify-between min-h-[3.1rem] sm:h-24 relative overflow-hidden">
                    <span className="text-[8px] sm:text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                      NEW TODAY
                    </span>
                    <div className="flex items-baseline gap-1 sm:gap-2 mt-0.5 sm:mt-1">
                      <span className="text-sm sm:text-3xl font-extrabold text-zinc-100">
                        {newTodayCount}
                      </span>
                      <span className="text-[7.5px] sm:text-xs text-zinc-500 font-mono truncate">
                        5 platforms
                      </span>
                    </div>
                  </motion.div>

                  {/* Card 4: Research Hours Saved */}
                  <motion.div variants={itemVariants} className="nexa-card px-2.5 py-1.5 sm:p-4 flex flex-col justify-between min-h-[3.1rem] sm:h-24 relative overflow-hidden">
                    <span className="text-[8px] sm:text-[11px] font-bold uppercase tracking-wider text-zinc-500">
                      Research Hours Saved
                    </span>
                    <div className="flex items-baseline gap-1 sm:gap-2 mt-0.5 sm:mt-1">
                      <span className="text-sm sm:text-3xl font-extrabold text-[var(--nexa-accent)]">
                        {researchHoursSaved}h
                      </span>
                      <span className="text-[7.5px] sm:text-xs text-black dark:text-zinc-100 font-mono font-bold">
                        this week
                      </span>
                    </div>
                  </motion.div>
                </motion.div>

                {/* Lead Intelligence Grid */}
                <motion.div
                  className="flex flex-col flex-1 min-h-0"
                  variants={containerVariants}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4, duration: 0.5 }}
                >
                  <LeadTable
                    leads={leads}
                    selectedLeadId={selectedLeadId}
                    onSelectLead={setSelectedLeadId}
                    onLeadIngested={(newLead) =>
                      setLeads((prev) => {
                        const key = String(newLead.id || newLead.domain || newLead.company_name);
                        const exists = prev.some(
                          (l) => String(l.id || l.domain || l.company_name) === key
                        );
                        if (exists) {
                          return prev.map((l) =>
                            String(l.id || l.domain || l.company_name) === key ? newLead : l
                          );
                        }
                        return [newLead, ...prev];
                      })
                    }
                    onLeadDeleted={(id) => {
                      if (selectedLeadId === id) setSelectedLeadId(null);
                      setLeads(leads.filter((l) => l.id !== id));
                    }}
                    status={status}
                    externalSearchTerm={globalSearchTerm}
                    trackedLeadIds={trackedLeadIds}
                    onToggleTrackLead={handleToggleTrackLead}
                  />
                </motion.div>
              </>
            )}
          </main>
        </div>
      </div>

      {/* ===== GLASSMORPHIC FLOATING MOBILE BOTTOM NAVIGATION DOCK (Visible on screens < lg) ===== */}
      <nav className="mobile-bottom-dock">
        {mobileNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setCurrentView(item.key)}
              className={`flex flex-col items-center justify-center flex-1 w-1/4 py-1 px-1 rounded-full transition-all duration-300 ${
                isActive
                  ? 'bg-slate-900 text-white dark:bg-emerald-500 dark:text-slate-950 font-black shadow-md shadow-slate-900/30 dark:shadow-emerald-500/30'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white font-semibold'
              }`}
            >
              <Icon size={16} className={isActive ? 'stroke-[2.5]' : 'stroke-[1.8]'} />
              <span className="text-[8.5px] mt-0.5 tracking-tighter whitespace-nowrap text-center">
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>
    </>
  );
}
