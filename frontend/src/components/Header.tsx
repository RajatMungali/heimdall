import { Shield, Search, Bell, Sun, Moon, X } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface HeaderProps {
  status: 'loading' | 'success' | 'error';
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  isDark: boolean;
  setIsDark: (dark: boolean) => void;
  onToggleMobileSidebar?: () => void;
}

export default function Header({ status, searchTerm, setSearchTerm, isDark, setIsDark }: HeaderProps) {
  const [isMobileSearchOpen, setIsMobileSearchOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  
  const searchInputRef = useRef<HTMLInputElement>(null);
  const notificationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isMobileSearchOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isMobileSearchOpen]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="nexa-card nexa-card-no-hover relative z-10 flex items-center justify-between px-3 sm:px-5 py-2 sm:py-2.5 w-full rounded-2xl shadow-xs border border-nexa-border gap-2 sm:gap-4 overflow-hidden shrink-0">
      
      {/* 1. MOBILE ONLY: EXPANDED OVERLAY SEARCH (Spring animated on mobile viewports < sm) */}
      <AnimatePresence>
        {isMobileSearchOpen && (
          <motion.div
            initial={{ scaleX: 0.1, opacity: 0, originX: 1 }}
            animate={{ scaleX: 1, opacity: 1, originX: 1 }}
            exit={{ scaleX: 0.1, opacity: 0, originX: 1 }}
            transition={{ type: 'spring', damping: 25, stiffness: 350 }}
            className="absolute inset-0 z-30 flex items-center px-3 bg-white dark:bg-[#11111a] rounded-2xl border border-emerald-500/50 shadow-md sm:hidden"
          >
            <Search size={16} className="text-emerald-500 shrink-0 mr-2.5" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search leads, companies, signals..."
              className="w-full bg-transparent text-xs font-semibold text-slate-900 dark:text-zinc-100 outline-none placeholder:text-slate-400 dark:placeholder:text-zinc-500"
            />
            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                setIsMobileSearchOpen(false);
              }}
              className="flex items-center justify-center h-7 w-7 rounded-xl bg-slate-100 dark:bg-white/10 text-slate-500 hover:text-slate-950 dark:text-zinc-400 dark:hover:text-white shrink-0 ml-2 transition"
              aria-label="Close search"
            >
              <X size={15} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 2. LEFT SECTION: Company Logo, Name & Status Pill */}
      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        <div className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-xl shrink-0 overflow-hidden bg-transparent">
          <img
            src="/Lead Intelligence Logo.png"
            alt="Lead Intelligence Logo"
            className="w-full h-full object-contain rounded-xl"
          />
        </div>

        <div className="flex flex-col justify-center">
          <h1 className="text-xs sm:text-sm font-black tracking-tight text-slate-900 dark:text-zinc-100 leading-none">
            Prospector AI
          </h1>
          <div className="mt-0.5 text-[9px] sm:text-[10px] font-bold font-mono tracking-tight flex items-center gap-1">
            {status === 'loading' && (
              <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" /> Connecting…
              </span>
            )}
            {status === 'success' && (
              <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)] animate-pulse" /> Active
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

      {/* 3. DESKTOP CENTER SECTION: Full Static Search Bar (Visible on sm and up) */}
      <div className="hidden sm:flex flex-1 max-w-lg mx-4 min-w-[150px]">
        <div className="relative flex items-center w-full">
          <Search
            size={14}
            className="absolute left-3 text-slate-400 dark:text-zinc-400 pointer-events-none"
            aria-hidden="true"
          />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search leads, signals, intent topics..."
            className="w-full rounded-xl border border-slate-200 dark:border-white/10 bg-slate-100/80 dark:bg-white/5 py-1.5 pl-9 pr-8 text-xs font-medium text-slate-900 dark:text-zinc-100 outline-none transition-all placeholder:text-slate-400 dark:placeholder:text-zinc-400 focus:border-emerald-500/50 focus:bg-white dark:focus:bg-white/10 shadow-inner"
          />
          <kbd className="absolute right-2.5 inline-flex items-center gap-0.5 rounded-md border border-slate-200 dark:border-white/10 bg-white/60 dark:bg-white/10 px-1.5 py-0.5 text-[10px] font-mono font-bold text-slate-500 dark:text-zinc-400 pointer-events-none">
            /
          </kbd>
        </div>
      </div>

      {/* 4. RIGHT SECTION: Controls (Mobile compact search button + Desktop Notifications + Theme Toggle) */}
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {/* MOBILE ONLY: Glassmorphic Search Magnifying Glass Icon Button */}
        <button
          type="button"
          onClick={() => setIsMobileSearchOpen(true)}
          className="flex sm:hidden h-7 w-7 items-center justify-center rounded-xl border border-slate-200/80 dark:border-white/10 bg-white/70 dark:bg-white/5 text-slate-600 dark:text-zinc-300 hover:text-slate-950 dark:hover:text-white backdrop-blur-md transition shadow-xs"
          title="Search"
        >
          <Search size={15} />
        </button>

        {/* DESKTOP ONLY: Notification Bell (Hidden for now) */}
        {/* <div ref={notificationRef} className="relative hidden sm:block">...</div> */}

        {/* Theme Toggle (Visible on Desktop & Mobile) */}
        <button
          type="button"
          onClick={() => setIsDark(!isDark)}
          className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-xl border border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-zinc-300 hover:text-slate-950 dark:hover:text-white transition shrink-0"
          title={isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
        >
          {isDark ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  );
}
