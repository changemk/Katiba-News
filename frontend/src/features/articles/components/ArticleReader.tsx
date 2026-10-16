import React from 'react';

export const ArticleReader: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto my-8 px-4 sm:px-6 font-sans">
      
      {/* Top Navigation / Section Guide */}
      <div className="mb-6 flex items-center justify-between border-b border-slate-100 pb-4">
        <div className="text-[11px] font-bold tracking-widest text-indigo-600 uppercase">
          Constitutional Record / Archive
        </div>
        <div className="text-[11px] font-medium text-slate-400">
          Document Reference: Official Publication
        </div>
      </div>

      {/* Main Manuscript Card Container */}
      <article className="bg-white border border-slate-200 rounded-xl shadow-xs p-6 sm:p-10">
        
        {/* Document Classification Badge */}
        <div className="inline-block px-2.5 py-0.5 rounded-sm bg-slate-100 border border-slate-200 text-slate-600 text-[9px] font-bold tracking-wider uppercase mb-4">
          Verified Amendment Text
        </div>

        {/* Article Title */}
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight sm:text-4xl lg:text-5xl leading-tight mb-6">
          Constitutional Framework Update
        </h1>

        {/* Article Metadata Panel */}
        <div className="flex flex-wrap items-center gap-y-2 gap-x-4 text-xs text-slate-500 mb-8 pb-6 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 uppercase tracking-wider text-[10px] font-semibold">Author</span>
            <span className="font-semibold text-slate-800">Katiba-News Editorial Team</span>
          </div>
          <span className="hidden sm:inline text-slate-200">|</span>
          <div className="flex items-center gap-2">
            <span className="text-slate-400 uppercase tracking-wider text-[10px] font-semibold">Published</span>
            <span className="font-medium text-slate-700">September 21, 2026</span>
          </div>
          <span className="hidden sm:inline text-slate-200">|</span>
          <div className="flex items-center gap-2">
            <span className="text-slate-400 uppercase tracking-wider text-[10px] font-semibold">Status</span>
            <span className="font-bold text-emerald-700 uppercase tracking-wide text-[10px]">Live Data Stream</span>
          </div>
        </div>

        {/* Article Text Content Body & Humanized Loading Skeleton State */}
        <div className="text-slate-800 leading-relaxed text-base sm:text-lg space-y-6 font-serif max-w-none">
          <p className="font-sans text-sm text-slate-500 italic max-w-xl bg-slate-50 border-l-2 border-slate-300 p-4 rounded-r-lg">
            Synchronizing database nodes. Establishing structural handshakes with live remote models to populate verified legal article files...
          </p>
          
          {/* Subtle Abstract Humanized Visual Line Buffers to simulate text loading beautifully */}
          <div className="space-y-3 pt-4">
            <div className="h-4 bg-slate-100/80 rounded-sm w-full animate-pulse"></div>
            <div className="h-4 bg-slate-100/80 rounded-sm w-11/12 animate-pulse"></div>
            <div className="h-4 bg-slate-100/80 rounded-sm w-full animate-pulse"></div>
            <div className="h-4 bg-slate-100/80 rounded-sm w-4/5 animate-pulse"></div>
          </div>
        </div>

        {/* Content Footer Info */}
        <div className="mt-12 pt-6 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs text-slate-400">
          <span>End of active text record.</span>
          <span className="font-mono text-[11px]">System API Status: Connection Secure</span>
        </div>

      </article>
    </div>
  );
};
