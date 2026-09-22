import React from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  ExternalLink,
  Calendar,
  MessageSquare,
  Sparkles,
  Tag,
  User,
  Share2,
  CheckCircle2,
  Flame
} from 'lucide-react';
import type { SocialPost } from '../types/lead';

interface SocialPostDetailDrawerProps {
  post: SocialPost | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function SocialPostDetailDrawer({
  post,
  isOpen,
  onClose
}: SocialPostDetailDrawerProps) {
  if (!isOpen || !post) return null;

  const isPostHot = (p: SocialPost) => {
    const postDate = new Date(p.published_at);
    const now = new Date();
    if (!isNaN(postDate.getTime())) {
      const diffDays = Math.floor((now.getTime() - postDate.getTime()) / (1000 * 60 * 60 * 24));
      return diffDays < 10;
    }
    return true;
  };

  const isHot = isPostHot(post);

  const getPlatformLabel = (plat?: string) => {
    const p = (plat || '').toLowerCase();
    if (p.includes('reddit')) return 'Reddit';
    if (p.includes('linkedin')) return 'LinkedIn';
    if (p.includes('x') || p.includes('twitter')) return 'X (Twitter)';
    if (p.includes('threads')) return 'Threads';
    if (p.includes('instagram')) return 'Instagram';
    if (p.includes('facebook')) return 'Facebook';
    if (p.includes('yelp')) return 'Yelp';
    return p.toUpperCase() || 'SOCIAL';
  };

  const getPlatformBadgeColor = (plat?: string) => {
    const p = (plat || '').toLowerCase();
    if (p.includes('reddit')) return 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/30';
    if (p.includes('linkedin')) return 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30';
    if (p.includes('x') || p.includes('twitter')) return 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/30';
    if (p.includes('threads')) return 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30';
    if (p.includes('instagram')) return 'bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/30';
    return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30';
  };

  const formattedDate = (() => {
    try {
      const d = new Date(post.published_at.replace('Z', '+00:00'));
      return isNaN(d.getTime())
        ? post.published_at
        : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return post.published_at;
    }
  })();

  const rawContent = (post.content || '').replace(/["“”]/g, '').trim();
  const cleanContent = rawContent
    .replace(/^[^—–\n]+(?:\(@[^\)]+\)|•|\bInstagram\b|\bLinkedIn\b|\bTwitter\b|\bReddit\b|\bFacebook\b)[^—–\n]*[—–]\s*/gi, '')
    .replace(/^[^—–\n]*\(@[^\)]+\)[^—–\n]*[—–]\s*/gi, '')
    .trim();
  const displayContent = cleanContent || rawContent;
  const rawTitle = (post.summary || displayContent.split('\n')[0] || displayContent || '').replace(/^["“”']+|["“”']+$/g, '').trim();

  return createPortal(
    <AnimatePresence>
      <div className="fixed inset-0 z-[99999] flex justify-end">
        {/* BACKDROP */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-slate-900/40 dark:bg-black/60 backdrop-blur-xs transition-opacity"
        />

        {/* SLIDE-OVER DRAWER PANEL (40% WIDTH) */}
        <motion.aside
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 25, stiffness: 220 }}
          className="side-drawer-panel fixed right-0 top-0 bottom-0 w-full md:w-[40%] sm:min-w-[400px] max-w-full bg-white dark:bg-zinc-950 border-l border-slate-200 dark:border-zinc-800 shadow-2xl z-[100000] flex flex-col font-sans overflow-x-hidden"
        >
          {/* 1. DRAWER HEADER */}
          <div className="px-6 py-5 border-b border-slate-200 dark:border-zinc-800/80 bg-slate-50/50 dark:bg-zinc-900/40 flex items-start justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-teal-500/20 dark:from-emerald-500/20 dark:to-teal-500/30 border border-emerald-500/30 flex items-center justify-center shrink-0 shadow-sm mt-0.5">
                <MessageSquare className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
              </div>

              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold font-mono uppercase tracking-wider text-slate-500 dark:text-zinc-400">
                    {post.author_name || post.author_handle || getPlatformLabel(post.platform)}
                  </span>
                  {post.author_handle && (
                    <span className="text-xs text-slate-400 dark:text-zinc-500 font-mono">
                      {post.author_handle.startsWith('@') ? post.author_handle : `@${post.author_handle}`}
                    </span>
                  )}
                </div>
                <h2 className="text-lg font-black text-slate-900 dark:text-zinc-100 leading-snug tracking-tight mt-0.5 line-clamp-2">
                  "{rawTitle}"
                </h2>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-2 rounded-2xl text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors shrink-0"
              title="Close Drawer"
            >
              <X size={20} />
            </button>
          </div>

          {/* 2. DRAWER BODY CONTENT */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin">
            
            {/* BADGES & METADATA BAR */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className={`px-3 py-1 rounded-xl font-bold font-mono border ${getPlatformBadgeColor(post.platform)}`}>
                {getPlatformLabel(post.platform)}
              </span>

              {isHot ? (
                <span className="px-3 py-1 rounded-xl font-bold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                  <Flame size={13} className="text-emerald-500 shrink-0" />
                  <span>Hot Intent Signal</span>
                </span>
              ) : (
                <span className="px-3 py-1 rounded-xl font-bold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-500/30 flex items-center gap-1">
                  <Sparkles size={13} className="text-amber-500 shrink-0" />
                  <span>Warm Intent Signal</span>
                </span>
              )}

              {post.keyword_matched && (
                <span className="px-3 py-1 rounded-xl font-medium bg-slate-100 dark:bg-zinc-800/80 text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700/80 flex items-center gap-1">
                  <Tag size={12} className="text-slate-400 shrink-0" />
                  <span>{post.keyword_matched}</span>
                </span>
              )}
            </div>

            {/* PUBLISHED TIMESTAMP CARD */}
            <div className="p-4 rounded-2xl bg-slate-50 dark:bg-zinc-900/60 border border-slate-200/80 dark:border-zinc-800/80 flex items-center justify-between text-xs text-slate-600 dark:text-zinc-400">
              <div className="flex items-center gap-2">
                <Calendar size={15} className="text-emerald-500 shrink-0" />
                <span className="font-medium">Published Date</span>
              </div>
              <span className="font-semibold text-slate-900 dark:text-zinc-200">{formattedDate}</span>
            </div>

            {/* AI SUMMARY BANNER (IF AVAILABLE) */}
            {post.summary && (
              <div className="p-5 rounded-3xl bg-gradient-to-br from-emerald-500/10 via-teal-500/5 to-transparent border border-emerald-500/20 dark:border-emerald-500/30 space-y-2">
                <div className="flex items-center gap-2 text-xs font-black text-emerald-700 dark:text-emerald-400 uppercase tracking-wider">
                  <Sparkles size={15} className="text-emerald-500 shrink-0" />
                  <span>Executive Signal Summary</span>
                </div>
                <p className="text-xs font-medium text-slate-700 dark:text-zinc-300 leading-relaxed">
                  {post.summary}
                </p>
              </div>
            )}

            {/* VERBATIM POST CONTENT */}
            <div className="space-y-2.5">
              <h3 className="text-xs font-black text-slate-400 dark:text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                <Share2 size={13} className="text-emerald-500" />
                <span>Verbatim Post Content</span>
              </h3>
              <div className="p-5 rounded-3xl bg-slate-50 dark:bg-zinc-900/80 border border-slate-200/80 dark:border-zinc-800/80 text-slate-800 dark:text-zinc-200 text-xs leading-relaxed font-sans whitespace-pre-wrap">
                {displayContent}
              </div>
            </div>

            {/* AUTHOR DETAILS (IF AVAILABLE) */}
            {(post.author_name || post.author_handle || post.company_name) && (
              <div className="space-y-2.5">
                <h3 className="text-xs font-black text-slate-400 dark:text-zinc-500 uppercase tracking-wider flex items-center gap-1.5">
                  <User size={13} className="text-emerald-500" />
                  <span>Author & Organization Info</span>
                </h3>
                <div className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200/80 dark:border-zinc-800/80 space-y-2 text-xs">
                  {post.author_name && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500 dark:text-zinc-400">Author Name</span>
                      <span className="font-bold text-slate-900 dark:text-zinc-100">{post.author_name}</span>
                    </div>
                  )}
                  {post.author_handle && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500 dark:text-zinc-400">Handle / Profile</span>
                      <span className="font-mono text-emerald-600 dark:text-emerald-400">{post.author_handle}</span>
                    </div>
                  )}
                  {post.company_name && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500 dark:text-zinc-400">Associated Organization</span>
                      <span className="font-bold text-slate-900 dark:text-zinc-100">{post.company_name}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

          </div>

          {/* 3. DRAWER FOOTER ACTION */}
          {post.post_url && (
            <div className="p-5 border-t border-slate-200 dark:border-zinc-800/80 bg-slate-50/50 dark:bg-zinc-900/40">
              <a
                href={post.post_url}
                target="_blank"
                rel="noreferrer"
                className="w-full py-3 px-5 rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-sm shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer"
              >
                <span>View Original Post on {getPlatformLabel(post.platform)}</span>
                <ExternalLink size={16} />
              </a>
            </div>
          )}

        </motion.aside>
      </div>
    </AnimatePresence>,
    document.body
  );
}
