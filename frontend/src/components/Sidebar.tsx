import { LayoutGrid, Bookmark, Settings as SettingsIcon, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { createPortal } from 'react-dom';

const BriefcaseIcon = ({ size = 22, className = "" }: { size?: number; className?: string }) => (
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
    {/* Arched Top Handle */}
    <path d="M8 6V4.2C8 3 9 2 10.2 2h3.6C15 2 16 3 16 4.2V6" />
    {/* Rounded Briefcase Outer Body */}
    <rect x="2.5" y="6" width="19" height="15" rx="3.5" />
    {/* Curved Center Flap Strap */}
    <path d="M2.5 12.5C6 14.8 9.5 15.2 12 15.2C14.5 15.2 18 14.8 21.5 12.5" />
    {/* Center Clasp / Button */}
    <circle cx="12" cy="14.8" r="1.8" fill="currentColor" stroke="currentColor" strokeWidth="0.4" />
  </svg>
);

interface SidebarProps {
  currentView: string;
  setCurrentView: (view: string) => void;
  isDark?: boolean;
  setIsDark?: (dark: boolean) => void;
  status: 'loading' | 'success' | 'error';
  isMobileOpen?: boolean;
  setIsMobileOpen?: (open: boolean) => void;
}

export default function Sidebar({ currentView, setCurrentView, status, isMobileOpen = false, setIsMobileOpen }: SidebarProps) {
  const navItems = [
    { label: 'Dashboard', key: 'dashboard', icon: LayoutGrid },
    { label: 'Track Jobs', key: 'ats_jobs', icon: BriefcaseIcon },
    { label: 'Saved Leads', key: 'statistics', icon: Bookmark },
  ];

  const handleNavClick = (key: string) => {
    setCurrentView(key);
    if (setIsMobileOpen) {
      setIsMobileOpen(false);
    }
  };

  return (
    <>
      {/* ===== DESKTOP SIDEBAR (Visible on lg screens and up) ===== */}
      <div className="group relative w-[66px] shrink-0 hidden lg:block z-30">
        {/* Background Dim Overlay when hovering over desktop sidebar */}
        <div className="fixed inset-0 bg-slate-950/20 dark:bg-black/40 backdrop-blur-[1px] pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-30" />

        {/* Floating Desktop Overlay Sidebar */}
        <aside className="sidebar-container flex flex-col justify-between h-[calc(100vh-1.5rem)] w-[66px] group-hover:w-[255px] absolute top-0 left-0 transition-all duration-300 ease-in-out px-2 py-3.5 rounded-3xl font-sans z-30 overflow-hidden shadow-md group-hover:shadow-2xl border border-slate-200 dark:border-nexa-border">
          {/* 1. BRANDING: Prospector AI Name, Status & Shield Icon */}
          <div className="space-y-4 pt-1">
            <div className="flex items-center px-0 py-1 overflow-hidden transition-all duration-300">
              <div className="w-[46px] shrink-0 flex items-center justify-center">
                <div className="relative flex h-9 w-9 items-center justify-center rounded-2xl shrink-0 overflow-hidden bg-transparent">
                  <img
                    src="/Lead Intelligence Logo.png"
                    alt="Lead Intelligence Logo"
                    className="w-full h-full object-contain rounded-2xl"
                  />
                </div>
              </div>
              <div className="opacity-0 w-0 group-hover:w-auto group-hover:opacity-100 transition-all duration-300 whitespace-nowrap overflow-hidden group-hover:pl-2 flex flex-col justify-center">
                <h1 className="text-base font-black tracking-tight text-slate-900 dark:text-zinc-100 leading-none">
                  Prospector AI
                </h1>
                <div className="mt-1 text-[11px] font-bold font-mono tracking-tight flex items-center gap-1.5">
                  {status === 'loading' && (
                    <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" /> Connecting…
                    </span>
                  )}
                  {status === 'success' && (
                    <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)] animate-pulse" /> Engine Active
                    </span>
                  )}
                  {status === 'error' && (
                    <span className="text-rose-600 dark:text-rose-400 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> Disconnected
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="border-b border-transparent group-hover:border-slate-200 dark:group-hover:border-nexa-border transition-colors duration-300" />
          </div>

          {/* 2. NAVIGATION ITEMS */}
          <div className="flex-1 flex flex-col justify-start space-y-2.5 py-6">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentView === item.key;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => handleNavClick(item.key)}
                  className={`flex items-center rounded-2xl w-full text-left text-sm transition-all duration-200 overflow-hidden ${
                    isActive
                      ? 'bg-gradient-to-r from-emerald-100 via-emerald-50 to-teal-100/90 dark:from-emerald-950/70 dark:via-emerald-900/50 dark:to-teal-950/60 text-emerald-950 dark:text-emerald-300 border border-emerald-400/80 dark:border-emerald-500/40 shadow-[0_2px_12px_rgba(16,185,129,0.18)] font-black'
                      : 'text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-950 dark:hover:text-zinc-100 font-extrabold border border-transparent'
                  }`}
                >
                  <div className="w-[46px] h-[40px] shrink-0 flex items-center justify-center">
                    <Icon
                      size={22}
                      className={`transition-colors ${
                        isActive
                          ? 'text-emerald-900 dark:text-emerald-300 stroke-[2.5]'
                          : 'text-slate-600 dark:text-zinc-400 stroke-[2]'
                      }`}
                    />
                  </div>
                  <span className="opacity-0 w-0 group-hover:w-auto group-hover:opacity-100 transition-all duration-300 whitespace-nowrap group-hover:pl-1 pr-3">
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>

          {/* 3. SETTINGS AT BOTTOM */}
          <div className="pt-3 border-t border-transparent group-hover:border-slate-200 dark:group-hover:border-nexa-border transition-colors duration-300">
            <button
              type="button"
              onClick={() => handleNavClick('settings')}
              className={`flex items-center rounded-2xl w-full text-left text-sm transition-all duration-200 overflow-hidden ${
                currentView === 'settings'
                  ? 'bg-gradient-to-r from-emerald-100 via-emerald-50 to-teal-100/90 dark:from-emerald-950/70 dark:via-emerald-900/50 dark:to-teal-950/60 text-emerald-950 dark:text-emerald-300 border border-emerald-400/80 dark:border-emerald-500/40 shadow-[0_2px_12px_rgba(16,185,129,0.18)] font-black'
                  : 'text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-950 dark:hover:text-zinc-100 font-extrabold border border-transparent'
              }`}
            >
              <div className="w-[46px] h-[40px] shrink-0 flex items-center justify-center">
                <SettingsIcon
                  size={22}
                  className={`transition-colors ${
                    currentView === 'settings'
                      ? 'text-emerald-900 dark:text-emerald-300 stroke-[2.5]'
                      : 'text-slate-600 dark:text-zinc-400 stroke-[2]'
                  }`}
                />
              </div>
              <span className="opacity-0 w-0 group-hover:w-auto group-hover:opacity-100 transition-all duration-300 whitespace-nowrap group-hover:pl-1 pr-3 font-extrabold">
                Settings
              </span>
            </button>
          </div>
        </aside>
      </div>

      {/* ===== MOBILE SIDEBAR DRAWER (Rendered via Portal to top-level document.body) ===== */}
      {typeof document !== 'undefined' && createPortal(
        <AnimatePresence>
          {isMobileOpen && (
            <>
              {/* Backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setIsMobileOpen?.(false)}
                className="fixed inset-0 bg-slate-950/80 dark:bg-black/80 backdrop-blur-xs z-[9999999] lg:hidden"
              />

              {/* Slide-in Mobile Drawer */}
              <motion.aside
                initial={{ x: '-100%' }}
                animate={{ x: 0 }}
                exit={{ x: '-100%' }}
                transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                className="fixed top-0 left-0 bottom-0 w-[280px] max-w-[85vw] bg-white dark:bg-[#11111a] border-r border-slate-200 dark:border-nexa-border p-5 z-[9999999] lg:hidden font-sans flex flex-col justify-between overflow-y-auto"
              >
                <div>
                  {/* Header with Brand & Close Button */}
                  <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-200 dark:border-white/10">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-2xl shrink-0 overflow-hidden bg-transparent">
                        <img
                          src="/Lead Intelligence Logo.png"
                          alt="Lead Intelligence Logo"
                          className="w-full h-full object-contain rounded-2xl"
                        />
                      </div>
                      <div>
                        <h2 className="text-base font-black tracking-tight text-slate-900 dark:text-zinc-100">
                          Prospector AI
                        </h2>
                        <div className="text-[10px] font-bold font-mono tracking-tight">
                          {status === 'loading' && (
                            <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" /> Connecting…
                            </span>
                          )}
                          {status === 'success' && (
                            <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Active
                            </span>
                          )}
                          {status === 'error' && (
                            <span className="text-rose-600 dark:text-rose-400 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> Offline
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => setIsMobileOpen?.(false)}
                      className="p-2 rounded-xl text-slate-500 hover:text-slate-900 dark:text-zinc-400 dark:hover:text-white bg-slate-100 dark:bg-white/5 transition"
                      aria-label="Close sidebar menu"
                    >
                      <X size={18} />
                    </button>
                  </div>

                  {/* Mobile Navigation Links */}
                  <nav className="space-y-2 py-2">
                    {navItems.map((item) => {
                      const Icon = item.icon;
                      const isActive = currentView === item.key;
                      return (
                        <button
                          key={item.label}
                          type="button"
                          onClick={() => handleNavClick(item.key)}
                          className={`flex items-center gap-3 px-3.5 py-3 rounded-2xl w-full text-left text-sm font-bold transition ${
                            isActive
                              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md'
                              : 'text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-white/5'
                          }`}
                        >
                          <Icon size={20} className={isActive ? 'text-white' : 'text-slate-500 dark:text-zinc-400'} />
                          <span>{item.label}</span>
                        </button>
                      );
                    })}
                  </nav>
                </div>

                {/* Mobile Settings Button */}
                <div className="mt-auto pt-4 border-t border-slate-200 dark:border-white/10">
                  <button
                    type="button"
                    onClick={() => handleNavClick('settings')}
                    className={`flex items-center gap-3 px-3.5 py-3 rounded-2xl w-full text-left text-sm font-bold transition ${
                      currentView === 'settings'
                        ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md'
                        : 'text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-white/5'
                    }`}
                  >
                    <SettingsIcon size={20} className={currentView === 'settings' ? 'text-white' : 'text-slate-500 dark:text-zinc-400'} />
                    <span>Settings</span>
                  </button>
                </div>
              </motion.aside>
            </>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
}