import React, { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Trash2,
  Search,
  RefreshCw,
  MessageSquare,
  ChevronRight,
  Calendar,
  Sparkles,
  Flame,
  Globe
} from 'lucide-react';
import { fetchSocialPosts, deleteSocialPost, triggerSocialSweep } from '../lib/api';
import type { SocialPost } from '../types/lead';
import SocialPostDetailDrawer from './SocialPostDetailDrawer';

const TABS = ['All', 'Reddit', 'X', 'Facebook', 'LinkedIn', 'Threads'];

// Platform Brand Icon Components for Header Filter Tabs (Small Inline)
const HeaderRedditLogo = () => (
  <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="#FF4500">
    <circle cx="12" cy="12" r="10" />
    <path fill="#FFF" d="M16.67 13.14c.04.18.06.36.06.55 0 2.8-3.01 5.07-6.73 5.07s-6.73-2.27-6.73-5.07c0-.19.02-.37.06-.55A2.04 2.04 0 0 1 2 11.23c0-1.12.91-2.03 2.03-2.03.5 0 .96.18 1.32.48 1.4-.99 3.28-1.63 5.37-1.7l1.14-5.36 3.73.79c.08-.47.49-.83.98-.83 1.01 0 1.83.82 1.83 1.83s-.82 1.83-1.83 1.83c-.93 0-1.7-.7-1.81-1.61l-3.23-.69-.9 4.25c2.14.05 4.07.69 5.5 1.7.36-.31.82-.49 1.33-.49 1.12 0 2.03.91 2.03 2.03 0 .76-.42 1.42-1.04 1.77zM9.07 12.3c-.63 0-1.14.51-1.14 1.14s.51 1.14 1.14 1.14 1.14-.51 1.14-1.14-.51-1.14-1.14-1.14zm5.86 0c-.63 0-1.14.51-1.14 1.14s.51 1.14 1.14 1.14 1.14-.51 1.14-1.14-.51-1.14-1.14-1.14z"/>
  </svg>
);

const HeaderXLogo = () => (
  <svg className="w-3 h-3 shrink-0 fill-current" viewBox="0 0 24 24">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
);

const HeaderFacebookLogo = () => (
  <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" fill="#1877F2"/>
    <path fill="#FFF" d="M15 12h-2v7h-3v-7H8.5V9.5H10V8c0-2 1-3 3-3h2v2.5h-1c-.8 0-1 .2-1 1v1h2l-.5 2.5z"/>
  </svg>
);

const HeaderLinkedInLogo = () => (
  <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24">
    <rect width="20" height="20" x="2" y="2" fill="#0A66C2" rx="4"/>
    <path fill="#FFF" d="M6.5 8.5h2.5V17H6.5V8.5zM7.75 5C6.92 5 6.25 5.67 6.25 6.5S6.92 8 7.75 8 9.25 7.33 9.25 6.5 8.58 5 7.75 5zM11 8.5h2.4v1.2h.03c.33-.63 1.14-1.3 2.37-1.3 2.54 0 3 1.67 3 3.85V17h-2.5v-3.85c0-.92-.02-2.1-1.28-2.1-1.28 0-1.48 1-1.48 2.03V17H11V8.5z"/>
  </svg>
);

const HeaderThreadsLogo = () => (
  <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" fill="#000000"/>
    <path fill="#FFF" d="M14.88 11.53c-.1-.04-.26-.06-.5-.06-.41 0-.82.12-1.1.33-.3.23-.46.56-.46.94 0 .39.15.7.45.92.29.22.7.33 1.15.33.51 0 .95-.14 1.28-.43.34-.3.51-.72.51-1.24v-.25c0-.52-.16-.94-.48-1.24-.32-.3-.77-.45-1.35-.45h-.22c-.66 0-1.18.17-1.55.51-.37.34-.56.81-.56 1.4 0 .58.19 1.05.57 1.39.38.34.9.51 1.57.51.6 0 1.1-.14 1.5-.42.4-.28.6-.68.6-1.2h1.4c0 .87-.33 1.55-.99 2.04-.66.49-1.5.73-2.51.73-1.09 0-1.95-.3-2.58-.9-.63-.6-.94-1.43-.94-2.49 0-1.07.31-1.9.94-2.5.63-.6 1.49-.9 2.58-.9h.3c1.07 0 1.9.29 2.5.87.6.58.9 1.36.9 2.34v.53c0 .86-.28 1.53-.84 2.01-.56.48-1.3.72-2.22.72-.8 0-1.47-.19-2-.57-.53-.38-.8-.92-.8-1.62 0-.68.27-1.21.81-1.58.54-.37 1.25-.56 2.13-.56h.31v-.05z"/>
  </svg>
);

function getHeaderTabIcon(tab?: string) {
  if (!tab) return null;
  switch (tab.toLowerCase()) {
    case 'reddit': return <HeaderRedditLogo />;
    case 'x':
    case 'twitter': return <HeaderXLogo />;
    case 'facebook': return <HeaderFacebookLogo />;
    case 'linkedin': return <HeaderLinkedInLogo />;
    case 'threads': return <HeaderThreadsLogo />;
    default: return null;
  }
}

// Platform Brand Icon Components for Cards (Full Fill 24x24)
const RedditLogo = () => (
  <svg className="w-full h-full shrink-0" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="12" fill="#FF4500" />
    <path fill="#FFF" d="M16.67 13.14c.04.18.06.36.06.55 0 2.8-3.01 5.07-6.73 5.07s-6.73-2.27-6.73-5.07c0-.19.02-.37.06-.55A2.04 2.04 0 0 1 2 11.23c0-1.12.91-2.03 2.03-2.03.5 0 .96.18 1.32.48 1.4-.99 3.28-1.63 5.37-1.7l1.14-5.36 3.73.79c.08-.47.49-.83.98-.83 1.01 0 1.83.82 1.83 1.83s-.82 1.83-1.83 1.83c-.93 0-1.7-.7-1.81-1.61l-3.23-.69-.9 4.25c2.14.05 4.07.69 5.5 1.7.36-.31.82-.49 1.33-.49 1.12 0 2.03.91 2.03 2.03 0 .76-.42 1.42-1.04 1.77zM9.07 12.3c-.63 0-1.14.51-1.14 1.14s.51 1.14 1.14 1.14 1.14-.51 1.14-1.14-.51-1.14-1.14-1.14zm5.86 0c-.63 0-1.14.51-1.14 1.14s.51 1.14 1.14 1.14 1.14-.51 1.14-1.14-.51-1.14-1.14-1.14z"/>
  </svg>
);

const XLogo = () => (
  <svg className="w-full h-full shrink-0 p-2.5 bg-black text-white" viewBox="0 0 24 24">
    <path fill="currentColor" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
);

const FacebookLogo = () => (
  <svg className="w-full h-full shrink-0" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="12" fill="#1877F2"/>
    <path fill="#FFF" d="M15 12h-2v7h-3v-7H8.5V9.5H10V8c0-2 1-3 3-3h2v2.5h-1c-.8 0-1 .2-1 1v1h2l-.5 2.5z"/>
  </svg>
);

const LinkedInLogo = () => (
  <svg className="w-full h-full shrink-0" viewBox="0 0 24 24">
    <rect width="24" height="24" x="0" y="0" fill="#0A66C2"/>
    <path fill="#FFF" d="M6.5 8.5h2.5V17H6.5V8.5zM7.75 5C6.92 5 6.25 5.67 6.25 6.5S6.92 8 7.75 8 9.25 7.33 9.25 6.5 8.58 5 7.75 5zM11 8.5h2.4v1.2h.03c.33-.63 1.14-1.3 2.37-1.3 2.54 0 3 1.67 3 3.85V17h-2.5v-3.85c0-.92-.02-2.1-1.28-2.1-1.28 0-1.48 1-1.48 2.03V17H11V8.5z"/>
  </svg>
);

const ThreadsLogo = () => (
  <svg className="w-full h-full shrink-0" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="12" fill="#000000"/>
    <path fill="#FFF" d="M14.88 11.53c-.1-.04-.26-.06-.5-.06-.41 0-.82.12-1.1.33-.3.23-.46.56-.46.94 0 .39.15.7.45.92.29.22.7.33 1.15.33.51 0 .95-.14 1.28-.43.34-.3.51-.72.51-1.24v-.25c0-.52-.16-.94-.48-1.24-.32-.3-.77-.45-1.35-.45h-.22c-.66 0-1.18.17-1.55.51-.37.34-.56.81-.56 1.4 0 .58.19 1.05.57 1.39.38.34.9.51 1.57.51.6 0 1.1-.14 1.5-.42.4-.28.6-.68.6-1.2h1.4c0 .87-.33 1.55-.99 2.04-.66.49-1.5.73-2.51.73-1.09 0-1.95-.3-2.58-.9-.63-.6-.94-1.43-.94-2.49 0-1.07.31-1.9.94-2.5.63-.6 1.49-.9 2.58-.9h.3c1.07 0 1.9.29 2.5.87.6.58.9 1.36.9 2.34v.53c0 .86-.28 1.53-.84 2.01-.56.48-1.3.72-2.22.72-.8 0-1.47-.19-2-.57-.53-.38-.8-.92-.8-1.62 0-.68.27-1.21.81-1.58.54-.37 1.25-.56 2.13-.56h.31v-.05z"/>
  </svg>
);

function getTabIcon(tab?: string) {
  if (!tab) return null;
  switch (tab.toLowerCase()) {
    case 'reddit': return <RedditLogo />;
    case 'x':
    case 'twitter': return <XLogo />;
    case 'facebook': return <FacebookLogo />;
    case 'linkedin': return <LinkedInLogo />;
    case 'threads': return <ThreadsLogo />;
    default: return null;
  }
}

function timeAgo(dateString: string | number) {
  if (!dateString) return 'Just now';
  let t = 0;
  if (typeof dateString === 'number') {
    t = dateString;
  } else if (!isNaN(Number(dateString))) {
    t = Number(dateString);
  } else {
    t = new Date(dateString).getTime();
  }
  if (isNaN(t) || t <= 0) return 'Just now';
  if (t < 10000000000) t = t * 1000;

  const seconds = Math.floor((Date.now() - t) / 1000);
  if (isNaN(seconds) || seconds < 60) return 'Just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w ago`;
}

function isPostOlderThan30Days(post: SocialPost): boolean {
  let t = 0;
  const dateStr = post.published_at || (post as any).created_at;
  if (!dateStr) return false;
  if (!isNaN(Number(dateStr))) {
    t = Number(dateStr);
  } else {
    t = new Date(dateStr).getTime();
  }
  if (isNaN(t) || t <= 0) return false;
  if (t < 10000000000) t = t * 1000;
  
  const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;
  return (Date.now() - t) > thirtyDaysMs;
}

function formatLastFetched(date: Date | null): string {
  if (!date) return 'Just now';
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 15) return 'Just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function SocialPostsView() {
  const [posts, setPosts] = useState<SocialPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [activeTab, setActiveTab] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPost, setSelectedPost] = useState<SocialPost | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const [lastFetchedTime, setLastFetchedTime] = useState<Date | null>(() => {
    const saved = localStorage.getItem('social_posts_last_fetched');
    if (saved) {
      const parsed = new Date(saved);
      if (!isNaN(parsed.getTime())) {
        if (Date.now() - parsed.getTime() < 24 * 60 * 60 * 1000) {
          return parsed;
        }
      }
    }
    return new Date();
  });
  const [timeAgoText, setTimeAgoText] = useState<string>('Just now');

  useEffect(() => {
    const updateText = () => {
      setTimeAgoText(formatLastFetched(lastFetchedTime));
    };
    updateText();
    const interval = setInterval(updateText, 5000);
    return () => clearInterval(interval);
  }, [lastFetchedTime]);

  const loadPosts = async () => {
    setLoading(true);
    try {
      const data = await fetchSocialPosts(activeTab === 'All' ? undefined : activeTab.toLowerCase());
      setPosts(data);

      const saved = localStorage.getItem('social_posts_last_fetched');
      if (saved) {
        const parsed = new Date(saved);
        if (!isNaN(parsed.getTime()) && Date.now() - parsed.getTime() < 24 * 60 * 60 * 1000) {
          setLastFetchedTime(parsed);
          return;
        }
      }
      if (data && data.length > 0) {
        const sorted = [...data].sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime());
        const newest = new Date(sorted[0].published_at);
        if (!isNaN(newest.getTime())) {
          setLastFetchedTime(newest);
          localStorage.setItem('social_posts_last_fetched', newest.toISOString());
          return;
        }
      }
      const defaultTime = new Date();
      setLastFetchedTime(defaultTime);
      localStorage.setItem('social_posts_last_fetched', defaultTime.toISOString());
    } catch (err) {
      console.error('Failed to load posts', err);
      const defaultTime = new Date();
      setLastFetchedTime(defaultTime);
      localStorage.setItem('social_posts_last_fetched', defaultTime.toISOString());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPosts();
  }, [activeTab]);

  const handleFetch = async () => {
    setFetching(true);
    const clickTime = new Date();
    setLastFetchedTime(clickTime);
    localStorage.setItem('social_posts_last_fetched', clickTime.toISOString());

    try {
      await triggerSocialSweep();
      const fetchTime = new Date();
      setLastFetchedTime(fetchTime);
      localStorage.setItem('social_posts_last_fetched', fetchTime.toISOString());
      await loadPosts();
    } catch (err) {
      console.error('Failed to trigger sweep', err);
    } finally {
      setFetching(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setPosts((prev) => prev.filter((p) => p.id !== id));
    try {
      await deleteSocialPost(id);
    } catch (err) {
      console.error('Failed to delete post', err);
      loadPosts();
    }
  };

  const filteredPosts = useMemo(() => {
    let list = posts.filter((p) => !isPostOlderThan30Days(p));
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (p) =>
          p.content.toLowerCase().includes(q) ||
          p.company_name?.toLowerCase().includes(q) ||
          p.author_name?.toLowerCase().includes(q) ||
          p.author_handle?.toLowerCase().includes(q) ||
          p.keyword_matched?.toLowerCase().includes(q)
      );
    }
    return [...list].sort((a, b) => {
      const timeA = a.published_at ? new Date(a.published_at).getTime() : 0;
      const timeB = b.published_at ? new Date(b.published_at).getTime() : 0;
      return timeB - timeA;
    });
  }, [posts, searchQuery]);

  const isPostHot = (post: SocialPost) => {
    const postDate = new Date(post.published_at);
    const now = new Date();
    if (!isNaN(postDate.getTime())) {
      const diffDays = Math.floor((now.getTime() - postDate.getTime()) / (1000 * 60 * 60 * 24));
      return diffDays < 10;
    }
    return true;
  };

  const getPlatformBadgeColor = (plat?: string) => {
    const p = (plat || '').toLowerCase();
    if (p.includes('reddit')) return 'bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/30';
    if (p.includes('linkedin')) return 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30';
    if (p.includes('x') || p.includes('twitter')) return 'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/30';
    if (p.includes('threads')) return 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/30';
    if (p.includes('instagram')) return 'bg-pink-500/10 text-pink-700 dark:text-pink-400 border-pink-500/30';
    return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30';
  };

  return (
    <div className="flex-1 text-slate-900 dark:text-zinc-100 p-2 sm:p-4 md:p-6 font-sans space-y-6 bg-transparent">
      
      {/* 1. HEADER BAR & TRIGGER ACTION (Matching ATSJobsView header) */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/70 dark:bg-zinc-900/60 p-6 rounded-3xl border border-slate-200/80 dark:border-zinc-800/80 shadow-sm backdrop-blur-md">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
              <MessageSquare size={22} />
            </div>
            <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-zinc-100">
              Social Media Signals
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium pl-0.5">
            Real-time intent detection across Reddit, LinkedIn, X, Threads, and social communities.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleFetch}
            disabled={fetching}
            className={`px-5 py-2.5 rounded-2xl font-bold text-sm text-white shadow-md transition-all duration-200 flex items-center gap-2 ${
              fetching
                ? 'bg-slate-400 dark:bg-zinc-700 cursor-not-allowed'
                : 'bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20 hover:shadow-emerald-500/30 hover:scale-[1.02] active:scale-[0.98]'
            }`}
          >
            <RefreshCw size={16} className={fetching ? 'animate-spin' : ''} />
            {fetching ? 'Sweeping Social Signals...' : 'Fetch Intent Posts'}
          </button>
        </div>
      </div>

      {/* 2. STATS & PLATFORM TABS BAR */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white/60 dark:bg-zinc-900/40 p-3.5 rounded-2xl border border-slate-200/80 dark:border-zinc-800/80 backdrop-blur-md">
        
        {/* PLATFORM FILTER TABS */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto scrollbar-none">
          {TABS.map((tab) => {
            const isActive = activeTab === tab;
            const icon = getHeaderTabIcon(tab);
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  isActive
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'bg-slate-100 dark:bg-zinc-800/80 text-slate-600 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700/80'
                }`}
              >
                {icon}
                <span>{tab}</span>
              </button>
            );
          })}
        </div>

        {/* METRICS CAPSULES */}
        <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto shrink-0">
          <div className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-zinc-800 text-xs font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
            <span className="text-slate-400">Posts:</span>
            <span className="text-emerald-600 dark:text-emerald-400">{filteredPosts.length}</span>
          </div>

          <div className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-zinc-800 text-xs font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
            <span className="text-slate-400">Hot:</span>
            <span className="text-emerald-600 dark:text-emerald-400">{filteredPosts.filter(isPostHot).length}</span>
          </div>

          <div className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-zinc-800 text-xs font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
            <span className="text-slate-400 font-mono">Last Swept:</span>
            <span className="text-slate-900 dark:text-zinc-100">{timeAgoText}</span>
          </div>
        </div>

      </div>

      {/* 3. CONTENT FEED GRID (EXACTLY MATCHING ATS JOB POST CARD UI) */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-3">
          <RefreshCw className="animate-spin text-emerald-500" size={28} />
          <p className="text-xs font-medium text-slate-400">Loading social signals...</p>
        </div>
      ) : filteredPosts.length === 0 ? (
        <div className="bg-white/60 dark:bg-zinc-900/40 rounded-3xl p-12 text-center border border-slate-200/80 dark:border-zinc-800/80 max-w-md mx-auto my-8 backdrop-blur-md space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center mx-auto">
            <MessageSquare size={22} />
          </div>
          <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100">No social signals found</h3>
          <p className="text-xs text-slate-500 dark:text-zinc-400">
            Click 'Fetch Intent Posts' to trigger a fresh social media signal sweep!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPosts.map((post) => {
            const rawContent = (post.content || '').replace(/["“”]/g, '').trim();
            const cleanContent = rawContent
              .replace(/^[^—–\n]+(?:\(@[^\)]+\)|•|\bInstagram\b|\bLinkedIn\b|\bTwitter\b|\bReddit\b|\bFacebook\b)[^—–\n]*[—–]\s*/gi, '')
              .replace(/^[^—–\n]*\(@[^\)]+\)[^—–\n]*[—–]\s*/gi, '')
              .trim();
            
            const displayContent = cleanContent || rawContent;
            const rawTitle = (post.summary || displayContent.split('\n')[0] || displayContent || '').replace(/^["“”']+|["“”']+$/g, '').trim();
            const titleText = `"${rawTitle}"`;
            const snippetText = post.summary ? displayContent : (displayContent.split('\n').slice(1).join(' ') || displayContent);
            const isHot = isPostHot(post);

            return (
              <motion.div
                key={post.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                onClick={() => {
                  setSelectedPost(post);
                  setIsDrawerOpen(true);
                }}
                className="group relative bg-white dark:bg-zinc-900/70 hover:bg-slate-50/80 dark:hover:bg-zinc-900 border border-slate-200/90 dark:border-zinc-800 hover:border-emerald-500/40 dark:hover:border-emerald-500/40 p-5 rounded-3xl shadow-xs hover:shadow-md transition-all duration-200 cursor-pointer flex flex-col justify-between"
              >
                <div className="space-y-3">

                  {/* CARD TOP HEADER */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full overflow-hidden bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 flex items-center justify-center shrink-0 shadow-xs">
                        {getTabIcon(post.platform) || <MessageSquare size={20} className="text-slate-400 dark:text-zinc-500" />}
                      </div>
                      <div>
                        <span className="text-[11px] font-bold font-mono text-slate-400 dark:text-zinc-500 uppercase tracking-wider block truncate max-w-[150px]">
                          {post.author_name || post.author_handle || post.platform}
                        </span>
                        <h3 className="text-sm font-black text-slate-900 dark:text-zinc-100 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors line-clamp-1">
                          {titleText}
                        </h3>
                      </div>
                    </div>

                    <button
                      onClick={(e) => handleDelete(post.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-400 hover:text-rose-500 transition-all rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/30"
                      title="Delete card"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>

                  {/* BADGES ROW */}
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                    <span className={`px-2 py-0.5 rounded-lg font-bold font-mono border ${getPlatformBadgeColor(post.platform)}`}>
                      {post.platform?.toUpperCase() || 'SOCIAL'}
                    </span>
                    {isHot ? (
                      <span className="px-2 py-0.5 rounded-lg font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300">
                        Hot Signal
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-lg font-medium bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300">
                        Warm Signal
                      </span>
                    )}
                    <span className="px-2 py-0.5 rounded-lg font-medium bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300 flex items-center gap-1">
                      <Calendar size={11} className="text-slate-400 shrink-0" />
                      <span>{timeAgo(post.published_at)}</span>
                    </span>
                  </div>

                  {/* SUMMARY PREVIEW */}
                  <p className="text-xs text-slate-500 dark:text-zinc-400 line-clamp-2 leading-relaxed pt-1 border-t border-slate-100 dark:border-zinc-800/60">
                    {snippetText}
                  </p>
                </div>

                {/* CARD FOOTER LINK */}
                <div className="pt-3 mt-3 border-t border-slate-100 dark:border-zinc-800/60 flex items-center justify-between text-xs font-bold text-emerald-600 dark:text-emerald-400 group-hover:translate-x-0.5 transition-transform">
                  <span>View Full Signal Details</span>
                  <ChevronRight size={16} />
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* RIGHT DETAIL DRAWER */}
      <SocialPostDetailDrawer
        post={selectedPost}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />

    </div>
  );
}
