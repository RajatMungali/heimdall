import { Shield, Key, Bell, Database, Target, Save, Loader2, Cpu, Wand2, Sliders, Check, RefreshCw, ChevronDown, ChevronUp, History, Sparkles, Clock, Trash2, MessageSquare, Lock, Users } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { fetchIntents, updateIntents, generateICPWithAI, runPipeline, type IntentConfig, type AIICPResponse } from '../lib/api';

const DEFAULT_TEMPLATES = [
  {
    title: 'Recruitment Agency ICP',
    desc: 'Tech recruitment, engineering, ML (50-2000 emp)',
    niche: 'recruitment',
  },
];


export default function Settings() {
  const [intents, setIntents] = useState<IntentConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  // Local raw text states to allow typing commas, spaces, and newlines smoothly
  const [rawKeywords, setRawKeywords] = useState('');
  const [rawTriggers, setRawTriggers] = useState('');
  const [rawTopics, setRawTopics] = useState('');
  const [rawNews, setRawNews] = useState('');
  const [rawSerper, setRawSerper] = useState('');
  const [rawJobspy, setRawJobspy] = useState('');
  const [rawExaQuery, setRawExaQuery] = useState('');
  const [minEmployees, setMinEmployees] = useState(10);
  const [maxEmployees, setMaxEmployees] = useState(2000);
  const [minArr, setMinArr] = useState('$5M');
  const [maxArr, setMaxArr] = useState('$50M');
  const [rawTargetIndustries, setRawTargetIndustries] = useState('');
  const [rawDecisionMakerTitles, setRawDecisionMakerTitles] = useState('');
  const [savingTitles, setSavingTitles] = useState(false);
  const [savedTitlesSuccess, setSavedTitlesSuccess] = useState(false);

  // AI Assistant states
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiSummary, setAiSummary] = useState<string | null>(null);

  // Collapsible configuration panel state (Closed by default)
  const [configOpen, setConfigOpen] = useState(false);
  const configSectionRef = useRef<HTMLDivElement>(null);

  // Hidden/Discreet Pipeline Execution state
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineStatusText, setPipelineStatusText] = useState<string | null>(null);

  const handleExecutePipeline = async () => {
    if (pipelineRunning) return;
    setPipelineRunning(true);
    setPipelineStatusText('Sweeping signals...');
    try {
      const res = await runPipeline();
      const count = res?.qualified_count ?? res?.processed_count ?? 0;
      setPipelineStatusText(`Sync complete (${count} leads processed)`);
      setTimeout(() => setPipelineStatusText(null), 4000);
    } catch (e) {
      console.error('Pipeline execution error:', e);
      setPipelineStatusText('Sweep completed');
      setTimeout(() => setPipelineStatusText(null), 4000);
    } finally {
      setPipelineRunning(false);
    }
  };

  // ICP History state (Persisted in localStorage)
  const [historyICPs, setHistoryICPs] = useState<Array<{ title: string; prompt: string; date: string }>>([]);

  useEffect(() => {
    // Load local storage history
    try {
      const savedHistory = localStorage.getItem('heimdall_icp_history');
      if (savedHistory) {
        setHistoryICPs(JSON.parse(savedHistory));
      }
    } catch (e) {
      console.error('Failed to parse ICP history', e);
    }

    fetchIntents().then(data => {
      setIntents(data);
      setRawKeywords((data.extraction_keywords || []).join(', '));
      setRawTriggers((data.social_triggers || []).join(', '));
      setRawTopics((data.social_topics || []).join(', '));
      setRawNews((data.news_queries || []).join('\n'));
      setRawSerper((data.serper_queries || []).join('\n'));
      setRawJobspy(data.jobspy_search_term || '');
      setRawExaQuery(data.exa_query || 'multi-location franchise, healthcare, home services, or B2B companies in the US that recently opened a new location, expanded operations, or scaled revenue to $5M-$20M without a listed in-house marketing director');
      setMinEmployees(data.min_employees || 10);
      setMaxEmployees(data.max_employees || 2000);
      setMinArr(data.min_arr || '$5M');
      setMaxArr(data.max_arr || '$50M');
      setRawTargetIndustries((data.target_industries || []).join(', '));
      setRawDecisionMakerTitles((data.decision_maker_titles || []).join('\n'));
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  const saveToHistory = (promptText: string) => {
    if (!promptText.trim()) return;
    const shortTitle = promptText.length > 35 ? promptText.slice(0, 35) + '...' : promptText;
    const newItem = {
      title: shortTitle,
      prompt: promptText,
      date: new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    };

    setHistoryICPs(prev => {
      const filtered = prev.filter(item => item.prompt.toLowerCase() !== promptText.toLowerCase());
      const updated = [newItem, ...filtered].slice(0, 6);
      try {
        localStorage.setItem('heimdall_icp_history', JSON.stringify(updated));
      } catch (e) {
        console.error(e);
      }
      return updated;
    });
  };

  const handleClearHistory = () => {
    setHistoryICPs([]);
    localStorage.removeItem('heimdall_icp_history');
  };

  const handleSaveDecisionMakerTitles = async () => {
    if (!intents) return;
    setSavingTitles(true);
    setSavedTitlesSuccess(false);
    const titlesArray = rawDecisionMakerTitles.split('\n').map(s => s.trim()).filter(Boolean);
    const updated: IntentConfig = {
      ...intents,
      decision_maker_titles: titlesArray,
    };
    try {
      const saved = await updateIntents(updated);
      setIntents(saved);
      setSavedTitlesSuccess(true);
      setTimeout(() => setSavedTitlesSuccess(false), 2500);
    } catch (err) {
      console.error('Failed to save decision maker titles:', err);
    } finally {
      setSavingTitles(false);
    }
  };

  const handleSaveIntents = async () => {
    setSaving(true);
    const payloadToSave: IntentConfig = {
      extraction_keywords: rawKeywords.split(',').map(s => s.trim()).filter(Boolean),
      social_triggers: rawTriggers.split(',').map(s => s.trim()).filter(Boolean),
      social_topics: rawTopics.split(',').map(s => s.trim()).filter(Boolean),
      news_queries: rawNews.split('\n').map(s => s.trim()).filter(Boolean),
      serper_queries: rawSerper.split('\n').map(s => s.trim()).filter(Boolean),
      jobspy_search_term: rawJobspy.trim(),
      exa_query: rawExaQuery.trim(),
      news_signals_query_template: intents?.news_signals_query_template || '',
      min_employees: minEmployees,
      max_employees: maxEmployees,
      min_arr: minArr.trim(),
      max_arr: maxArr.trim(),
      target_industries: rawTargetIndustries.split(',').map(s => s.trim()).filter(Boolean),
    };
    try {
      await updateIntents(payloadToSave);
      setIntents(payloadToSave);
      if (aiPrompt.trim()) {
        saveToHistory(aiPrompt.trim());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateAIICP = async (customPrompt?: string) => {
    const promptToUse = customPrompt || aiPrompt;
    if (!promptToUse.trim()) return;

    setAiGenerating(true);
    setAiSummary(null);
    try {
      const res: AIICPResponse = await generateICPWithAI(promptToUse);

      // Auto-populate all form fields dynamically while leaving them 100% editable
      if (res.jobspy_search_term) setRawJobspy(res.jobspy_search_term);
      if (res.exa_query) setRawExaQuery(res.exa_query);
      if (res.extraction_keywords?.length) setRawKeywords(res.extraction_keywords.join(', '));
      if (res.social_triggers?.length) setRawTriggers(res.social_triggers.join(', '));
      if (res.social_topics?.length) setRawTopics(res.social_topics.join(', '));
      if (res.news_queries?.length) setRawNews(res.news_queries.join('\n'));
      if (res.serper_queries?.length) setRawSerper(res.serper_queries.join('\n'));
      if (res.min_employees) setMinEmployees(res.min_employees);
      if (res.max_employees) setMaxEmployees(res.max_employees);
      if (res.min_arr) setMinArr(res.min_arr);
      if (res.max_arr) setMaxArr(res.max_arr);
      if (res.target_industries?.length) setRawTargetIndustries(res.target_industries.join(', '));

      setAiSummary(res.summary_explanation || 'Successfully auto-populated settings from your ICP brief.');

      // 1. Automatically expand the Intent Configuration Box
      setConfigOpen(true);

      // 2. Save into ICP History
      saveToHistory(promptToUse);

      // 3. Automatically scroll down smoothly for user to inspect and edit configuration
      setTimeout(() => {
        configSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 350);

    } catch (err) {
      console.error('Failed to generate AI ICP settings:', err);
      alert('Failed to generate ICP settings with AI. Please check server logs.');
    } finally {
      setAiGenerating(false);
    }
  };

  const parsedTriggers = rawTriggers.split(',').map(s => s.trim()).filter(Boolean);
  const parsedTopics = rawTopics.split(',').map(s => s.trim()).filter(Boolean);
  const previewQuery = `(${ (parsedTriggers.map(t => `"${t}"`).join(' OR ')) || '"looking for"' }) ${ (parsedTopics.map(t => `"${t}"`).join(' OR ')) || '"marketing agency"' }`;

  return (
    <div className="flex-1 overflow-y-auto px-1 sm:px-4 pb-28 lg:pb-12 font-sans">
      <div className="nexa-card nexa-card-no-hover p-3.5 sm:p-6 lg:p-8 space-y-4 sm:space-y-8 w-full max-w-7xl mx-auto">
        
        {/* Settings Page Header */}
        <div className="flex items-center justify-between border-b border-nexa-border pb-4 sm:pb-5">
          <div className="space-y-1">
            <h2 className="text-lg sm:text-2xl font-bold text-zinc-100 tracking-tight">Pipeline Settings</h2>
            <p className="text-[11px] sm:text-xs text-zinc-400 font-medium leading-normal">
              Configure autonomous search queries, ICP headcount thresholds, and AI co-pilot preferences.
            </p>
          </div>
        </div>

        {/* Disabled Notice Banner */}
        <div className="p-3 sm:p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs font-medium flex items-center gap-2.5 shadow-xs">
          <Lock size={16} className="text-amber-400 shrink-0" />
          <span>Client-facing ICP and keyword editing is temporarily disabled. Quick Enterprise Templates remain available below.</span>
        </div>

        {/* 1. AI ICP ASSISTANT CARD (UNCONGESTED, SPACIOUS CHAT BOX) */}
        <section className="side-drawer-card p-3.5 sm:p-6 border border-[var(--nexa-accent)]/30 bg-[var(--nexa-accent-dim)] rounded-2xl space-y-3 sm:space-y-5 shadow-sm">
          <div className="flex items-start sm:items-center gap-2.5 sm:gap-3">
            <div className="p-2 sm:p-2.5 rounded-xl bg-[var(--nexa-accent)] text-zinc-950 shadow-xs shrink-0 mt-0.5 sm:mt-0">
              <Cpu size={18} className="stroke-[2.5] sm:w-5 sm:h-5" />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-bold text-zinc-100 tracking-tight">
                AI ICP Assistant
              </h3>
              <p className="text-[11px] sm:text-xs text-zinc-300 font-medium leading-normal">
                Describe your Ideal Customer Profile in natural language. The AI will parse headcount, job terms, and intent queries automatically.
              </p>
            </div>
          </div>

          {/* Chat Input Box & Action */}
          <div className="flex flex-col sm:flex-row gap-2.5 sm:gap-3 pt-1">
            <textarea
              disabled
              className="flex-1 glass-input rounded-xl p-3 sm:p-3.5 text-xs text-zinc-100 placeholder-zinc-400 border border-white/10 bg-nexa-surface resize-none font-medium leading-relaxed opacity-60 cursor-not-allowed"
              rows={3}
              placeholder="Target marketing agency looking for SEO, ads opportunities headcount ≤5000"
              value={aiPrompt}
              onChange={e => setAiPrompt(e.target.value)}
            />
            <button
              disabled
              className="w-full sm:w-auto px-5 py-3 sm:py-4 rounded-xl font-bold text-xs bg-[var(--nexa-accent)]/50 text-zinc-950 flex items-center justify-center gap-2 sm:gap-2.5 whitespace-nowrap opacity-50 cursor-not-allowed shadow-md shrink-0"
            >
              <Wand2 size={16} />
              Generate & Populate
            </button>
          </div>

          {/* AI Response Summary */}
          {aiSummary && (
            <div className="p-3 sm:p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-[11px] sm:text-xs font-medium flex items-center gap-2 sm:gap-2.5 animate-fade-in">
              <Check size={15} className="text-emerald-400 shrink-0" />
              <span>{aiSummary} Intent Configuration has expanded below for your review & editing.</span>
            </div>
          )}
        </section>

        {/* 2. ICP TEMPLATES & SAVED HISTORY BOX */}
        <section className="side-drawer-card p-3.5 sm:p-6 rounded-2xl border border-nexa-border bg-nexa-surface space-y-3 sm:space-y-4 shadow-2xs">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <History size={14} className="text-[var(--nexa-accent)]" /> ICP Templates & Prompt History
            </h3>
            {historyICPs.length > 0 && (
              <button
                onClick={handleClearHistory}
                className="text-[11px] text-zinc-500 hover:text-zinc-300 flex items-center gap-1 transition font-medium"
                title="Clear Prompt History"
              >
                <Trash2 size={12} /> Clear History
              </button>
            )}
          </div>

          {/* Pre-configured Templates Row */}
          <div className="space-y-2.5">
            <span className="text-[11px] font-bold text-zinc-400 block uppercase tracking-wider">Select Active ICP Niche:</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {DEFAULT_TEMPLATES.map((tmpl, idx) => {
                const isActive = intents?.active_niche === tmpl.niche;
                return (
                  <button
                    key={idx}
                    onClick={async () => {
                      if (!intents) return;
                      setSaving(true);
                      const updated = {
                        ...intents,
                        active_niche: tmpl.niche,
                      };
                      try {
                        const saved = await updateIntents(updated);
                        setIntents(saved);
                      } catch (e) {
                        console.error('Failed to set active niche', e);
                      } finally {
                        setSaving(false);
                      }
                    }}
                    className={`side-drawer-pill p-3.5 rounded-xl border transition-all text-xs font-semibold flex flex-col gap-1.5 shadow-2xs text-left cursor-pointer ${
                      isActive 
                        ? 'border-emerald-500/60 bg-emerald-500/15 text-emerald-400 font-bold shadow-sm ring-1 ring-emerald-500/30' 
                        : 'border-[var(--nexa-accent)]/30 bg-[var(--nexa-accent-dim)] text-[var(--nexa-accent)] hover:bg-[var(--nexa-accent-glow)]'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="font-bold text-xs sm:text-sm">{tmpl.title}</span>
                      {isActive ? <Check size={14} className="shrink-0 text-emerald-400" /> : <Sparkles size={14} className="shrink-0 opacity-60" />}
                    </div>
                    <span className="text-[11px] opacity-75 font-normal leading-relaxed">{tmpl.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* User's Recent Prompt History Row */}
          {historyICPs.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-nexa-border">
              <span className="text-[11px] font-bold text-zinc-400 block uppercase tracking-wider flex items-center gap-1">
                <Clock size={12} /> Your Saved Recent ICP Prompts:
              </span>
              <div className="flex flex-wrap gap-2">
                {historyICPs.map((hist, idx) => (
                  <button
                    key={idx}
                    disabled
                    className="side-drawer-pill px-3 py-1.5 sm:px-3.5 sm:py-1.5 rounded-xl border border-nexa-border bg-nexa-surface text-zinc-400 text-xs font-medium flex items-center gap-2 shadow-2xs cursor-not-allowed opacity-60"
                  >
                    <span>{hist.title}</span>
                    <span className="text-[10px] text-zinc-500 font-mono">{hist.date}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* 3. TARGET COMPANY HEADCOUNT & INDUSTRY NICHE (ICP FILTER) */}
        <section className="space-y-3 sm:space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
            <Sliders size={14} /> Target Company Filters & Industry Niche
          </h3>
          <div className="side-drawer-card space-y-3.5 sm:space-y-4 p-3.5 sm:p-5 rounded-2xl border border-nexa-border bg-nexa-surface opacity-85">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              <div>
                <label className="block text-xs font-bold text-zinc-200 mb-1.5">Minimum Employee Headcount</label>
                <input
                  type="number"
                  disabled
                  className="w-full glass-input rounded-xl p-2.5 sm:p-3 text-xs text-zinc-100 border border-nexa-border bg-nexa-surface font-medium cursor-not-allowed opacity-60"
                  value={minEmployees}
                  onChange={e => setMinEmployees(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-zinc-200 mb-1.5">Maximum Employee Headcount</label>
                <input
                  type="number"
                  disabled
                  className="w-full glass-input rounded-xl p-2.5 sm:p-3 text-xs text-zinc-100 border border-nexa-border bg-nexa-surface font-medium cursor-not-allowed opacity-60"
                  value={maxEmployees}
                  onChange={e => setMaxEmployees(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-zinc-200 mb-1.5">Minimum Target ARR</label>
                <input
                  type="text"
                  disabled
                  className="w-full glass-input rounded-xl p-2.5 sm:p-3 text-xs text-zinc-100 border border-nexa-border bg-nexa-surface font-medium cursor-not-allowed opacity-60"
                  placeholder="$5M"
                  value={minArr}
                  onChange={e => setMinArr(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-zinc-200 mb-1.5">Maximum Target ARR</label>
                <input
                  type="text"
                  disabled
                  className="w-full glass-input rounded-xl p-2.5 sm:p-3 text-xs text-zinc-100 border border-nexa-border bg-nexa-surface font-medium cursor-not-allowed opacity-60"
                  placeholder="$50M"
                  value={maxArr}
                  onChange={e => setMaxArr(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-zinc-200 mb-1.5">
                Target Industries & Specific ICP Niche (Comma-separated)
              </label>
              <input
                type="text"
                disabled
                className="w-full glass-input rounded-xl p-2.5 sm:p-3 text-xs text-zinc-100 border border-nexa-border bg-nexa-surface font-medium cursor-not-allowed opacity-60"
                placeholder="Fintech SaaS, B2B Software, Healthcare, Multi-Location Franchise, Home Services"
                value={rawTargetIndustries}
                onChange={e => setRawTargetIndustries(e.target.value)}
              />
              <p className="text-[11px] text-zinc-400 mt-1.5 font-medium leading-normal">
                The pipeline prompts use these specific target industries (e.g. Fintech SaaS) to score candidates matching your target profile.
              </p>
            </div>
          </div>
        </section>

        {/* 4. DECISION MAKER TITLES CONFIGURATION (PER-CLIENT ONBOARDING PRIORITY) */}
        <section className="space-y-3 sm:space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <Users size={14} className="text-emerald-400" /> Decision Maker Titles (Client Priority Order)
            </h3>
            <button
              type="button"
              onClick={handleSaveDecisionMakerTitles}
              disabled={savingTitles}
              className="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-sm transition disabled:opacity-50 cursor-pointer"
            >
              {savingTitles ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              <span>{savedTitlesSuccess ? 'Saved!' : 'Save Titles'}</span>
            </button>
          </div>

          <div className="side-drawer-card space-y-3.5 p-3.5 sm:p-5 rounded-2xl border border-nexa-border bg-nexa-surface">
            <div className="space-y-1">
              <label className="block text-xs font-bold text-zinc-200">
                Priority Titles (One per line, top = highest priority)
              </label>
              <p className="text-[11px] text-zinc-400 font-medium leading-normal">
                Configured during client onboarding. FullEnrich queries for these titles in a single search, and our LLM ranking layer maps and deduplicates candidates against this exact priority list.
              </p>
            </div>

            <textarea
              rows={7}
              className="w-full glass-input rounded-xl p-3 text-xs font-mono text-zinc-100 border border-nexa-border bg-nexa-surface resize-y leading-relaxed"
              placeholder={'Head of Talent Acquisition\nHead of Recruiting\nDirector of Talent Acquisition\nCEO'}
              value={rawDecisionMakerTitles}
              onChange={e => setRawDecisionMakerTitles(e.target.value)}
            />

            <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-zinc-500 font-mono">
              <span>{rawDecisionMakerTitles.split('\n').filter(s => s.trim()).length} priority titles configured</span>
              <span className="text-emerald-500 font-semibold">Semantic LLM matching active</span>
            </div>
          </div>
        </section>

        {/* 5. COLLAPSIBLE INTENT SIGNALS CONFIGURATION BOX (SCROLL TARGET) */}
        <section ref={configSectionRef} className="space-y-3 sm:space-y-4 pt-2">
          {/* Expandable Accordion Header */}
          <div
            onClick={() => setConfigOpen(!configOpen)}
            className="side-drawer-card p-3.5 sm:p-5 rounded-2xl border border-nexa-border bg-nexa-surface flex items-center justify-between cursor-pointer hover:border-[var(--nexa-accent)]/40 transition-all shadow-xs gap-2"
          >
            <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
              <div className="p-2 rounded-xl bg-indigo-950/80 text-indigo-300 border border-indigo-500/30 shrink-0">
                <Target size={16} />
              </div>
              <div className="min-w-0">
                <h3 className="text-xs sm:text-sm font-bold text-zinc-100 tracking-tight flex flex-wrap items-center gap-1.5 sm:gap-2">
                  <span>Intent Signals & Search Queries Configuration</span>
                  <span className="px-2 py-0.5 rounded-full text-[9px] sm:text-[10px] bg-nexa-surface border border-nexa-border text-zinc-400 font-mono font-normal shrink-0">
                    {configOpen ? 'Open / Read-Only' : 'Collapsed'}
                  </span>
                </h3>
                <p className="text-[11px] sm:text-xs text-zinc-400 font-medium leading-normal truncate sm:whitespace-normal">
                  Review job roles, extraction keywords, social triggers, and search queries.
                </p>
              </div>
            </div>

            <button className="p-1.5 sm:p-2 rounded-xl border border-nexa-border bg-nexa-surface text-zinc-400 hover:text-zinc-100 transition shrink-0">
              {configOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>

          {/* Collapsible Form Body */}
          {configOpen && (
            <div className="side-drawer-card p-3.5 sm:p-6 rounded-2xl border border-nexa-border bg-nexa-surface space-y-4 sm:space-y-5 animate-fade-in shadow-sm">
              {loading ? (
                <div className="flex items-center gap-2 text-zinc-400 text-xs py-4">
                  <Loader2 className="animate-spin" size={14} /> Loading intent configuration...
                </div>
              ) : intents ? (
                <>
                  {/* NEURAL SEARCH PROMPT */}
                  <div>
                    <label className="block text-xs font-bold text-zinc-200 mb-1.5 flex items-center justify-between">
                      <span>Neural Search Prompt (Phase 1 Discovery) — <span className="text-[var(--nexa-accent)] font-semibold">Auto-Generated</span></span>
                      <span className="text-[10px] text-zinc-400 font-mono font-normal">Used to fetch 100 high-intent leads</span>
                    </label>
                    <textarea
                      disabled
                      className="w-full glass-input rounded-xl p-3.5 text-xs text-zinc-100 border border-[var(--nexa-accent)]/40 bg-nexa-surface font-medium leading-relaxed cursor-not-allowed opacity-60"
                      rows={3}
                      value={rawExaQuery}
                      onChange={e => setRawExaQuery(e.target.value)}
                      placeholder="e.g. companies looking for a marketing agency, fractional CMO, PPC agency, or lead generation services, expanding operations or hiring growth leaders in the United States"
                    />
                  </div>

                  {/* SOCIAL SIGNALS PLATFORM QUERIES SECTION */}
                  <div className="pt-3 border-t border-nexa-border space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                        <MessageSquare size={14} className="text-amber-400" /> Social Signals Search Queries
                      </h4>
                      <span className="text-[11px] text-zinc-400 font-medium">Auto-compiled for each platform</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                      {/* 1. Google */}
                      <div className="p-3.5 rounded-xl border border-blue-500/20 bg-blue-500/5 space-y-1.5 flex flex-col opacity-85">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-blue-500" /> Google Search & Q&A
                          </span>
                        </div>
                        <textarea 
                          disabled
                          className="flex-1 w-full text-[11px] font-mono text-slate-800 dark:text-zinc-200 bg-white/80 dark:bg-black/40 p-2.5 rounded-lg border border-slate-200/80 dark:border-white/5 shadow-xs resize-none cursor-not-allowed opacity-60"
                          rows={2}
                          defaultValue={'site:linkedin.com/posts ("looking for web design agency" OR "website redesign RFP")'}
                        />
                      </div>

                      {/* 2. Reddit */}
                      <div className="p-3.5 rounded-xl border border-orange-500/20 bg-orange-500/5 space-y-1.5 flex flex-col opacity-85">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-orange-600 dark:text-orange-400 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-orange-500" /> Reddit Intent Scanner
                          </span>
                        </div>
                        <textarea 
                          disabled
                          className="flex-1 w-full text-[11px] font-mono text-slate-800 dark:text-zinc-200 bg-white/80 dark:bg-black/40 p-2.5 rounded-lg border border-slate-200/80 dark:border-white/5 shadow-xs resize-none cursor-not-allowed opacity-60"
                          rows={2}
                          defaultValue={previewQuery || 'Fractional CMO agency OR looking for Marketing Agency'}
                        />
                      </div>

                      {/* 3. LinkedIn */}
                      <div className="p-3.5 rounded-xl border border-sky-500/20 bg-sky-500/5 space-y-1.5 flex flex-col opacity-85">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-sky-600 dark:text-sky-400 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-sky-500" /> LinkedIn Posts & RFPs
                          </span>
                        </div>
                        <textarea 
                          disabled
                          className="flex-1 w-full text-[11px] font-mono text-slate-800 dark:text-zinc-200 bg-white/80 dark:bg-black/40 p-2.5 rounded-lg border border-slate-200/80 dark:border-white/5 shadow-xs resize-none cursor-not-allowed opacity-60"
                          rows={2}
                          defaultValue={'"looking for web design agency" OR "website redesign RFP"'}
                        />
                      </div>

                      {/* 4. X (Twitter) */}
                      <div className="p-3.5 rounded-xl border border-slate-300/40 dark:border-zinc-500/20 bg-slate-500/5 space-y-1.5 flex flex-col opacity-85">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-slate-500 dark:bg-zinc-400" /> X (Twitter) Real-time
                          </span>
                        </div>
                        <textarea 
                          disabled
                          className="flex-1 w-full text-[11px] font-mono text-slate-800 dark:text-zinc-200 bg-white/80 dark:bg-black/40 p-2.5 rounded-lg border border-slate-200/80 dark:border-white/5 shadow-xs resize-none cursor-not-allowed opacity-60"
                          rows={2}
                          defaultValue={previewQuery ? `${previewQuery} -is:retweet` : '("looking for" OR "recommend") ("web design" OR "website redesign") -is:retweet'}
                        />
                      </div>

                      {/* 5. Facebook */}
                      <div className="p-3.5 rounded-xl border border-blue-600/20 bg-blue-600/5 space-y-1.5 flex flex-col opacity-85">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-blue-600 dark:text-blue-300 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-blue-600" /> Facebook Groups & Public Posts
                          </span>
                        </div>
                        <textarea 
                          disabled
                          className="flex-1 w-full text-[11px] font-mono text-slate-800 dark:text-zinc-200 bg-white/80 dark:bg-black/40 p-2.5 rounded-lg border border-slate-200/80 dark:border-white/5 shadow-xs resize-none cursor-not-allowed opacity-60"
                          rows={2}
                          defaultValue={'"looking for website redesign agency" OR "recommend marketing agency"'}
                        />
                      </div>

                      {/* 6. Threads */}
                      <div className="p-3.5 rounded-xl border border-purple-500/20 bg-purple-500/5 space-y-1.5 flex flex-col opacity-85">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-purple-600 dark:text-purple-300 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-purple-500" /> Threads Micro-Posts
                          </span>
                        </div>
                        <textarea 
                          disabled
                          className="flex-1 w-full text-[11px] font-mono text-slate-800 dark:text-zinc-200 bg-white/80 dark:bg-black/40 p-2.5 rounded-lg border border-slate-200/80 dark:border-white/5 shadow-xs resize-none cursor-not-allowed opacity-60"
                          rows={2}
                          defaultValue={'"looking for web design agency" OR "need agency recommendation"'}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end pt-3">
                    <button
                      disabled
                      className="flex items-center justify-center gap-2 w-full sm:w-auto px-6 py-3 text-xs font-bold rounded-xl bg-[var(--nexa-accent)]/50 text-zinc-950 opacity-50 cursor-not-allowed shadow-md"
                    >
                      <Save size={14} />
                      Save Intent Configuration
                    </button>
                  </div>
                </>
              ) : (
                <div className="text-zinc-500 text-xs py-4">Failed to load intents configuration.</div>
              )}
            </div>
          )}
        </section>

        {/* Subtle Bottom Telemetry Footer / Pipeline Trigger */}
        <div className="pt-6 pb-2 border-t border-slate-200/60 dark:border-zinc-800/60 flex items-center justify-between text-[11px] text-slate-400 dark:text-zinc-500 font-mono select-none">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/80 inline-block animate-pulse" />
            <span className="text-[10px] tracking-tight">Telemetry v2.4 • System Active</span>
          </div>

          <button
            type="button"
            onClick={handleExecutePipeline}
            disabled={pipelineRunning}
            title="Synchronize Live Stream"
            className="group flex items-center gap-1.5 px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-700 dark:text-zinc-500 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800/40 transition-colors duration-150 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw size={10} className={`transition-transform duration-300 ${pipelineRunning ? 'animate-spin text-emerald-500' : 'group-hover:rotate-180 opacity-60'}`} />
            <span className="text-[10px] font-medium tracking-tight">
              {pipelineRunning ? (pipelineStatusText || 'Sweeping...') : (pipelineStatusText || 'Sync stream')}
            </span>
          </button>
        </div>

      </div>
    </div>
  );
}
