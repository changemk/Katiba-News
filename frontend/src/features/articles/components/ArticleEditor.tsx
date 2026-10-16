import React, { useState } from 'react';

export const ArticleEditor: React.FC = () => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('Constitution');

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;

  return (
    <div className="max-w-6xl mx-auto my-8 px-4 sm:px-6 font-sans">
      
      {/* Editorial Header Panel */}
      <div className="bg-slate-950 text-white rounded-xl p-6 sm:p-8 shadow-md mb-8 border border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="inline-block px-2.5 py-0.5 rounded-sm bg-indigo-950 border border-indigo-800 text-indigo-400 text-[10px] font-bold tracking-wider uppercase mb-3">
              Editorial Board Dashboard
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Draft Constitutional Updates
            </h1>
            <p className="text-slate-400 text-sm mt-1 max-w-xl leading-relaxed">
              Compose precise legal guides and amendment records. Drafts are processed sequentially through validation queue frameworks.
            </p>
          </div>
          
          {/* Status Indicator */}
          <div className="bg-slate-900 px-4 py-2.5 rounded border border-slate-800 self-start md:self-auto text-xs">
            <span className="text-slate-400 block text-[10px] uppercase tracking-wider font-semibold">Workspace Status</span>
            <span className="text-slate-200 font-medium">Ready to Sync</span>
          </div>
        </div>
      </div>

      {/* Workspace Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* LEFT COLUMN: Input Form Controls */}
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-6">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
            Document Composer
          </h2>

          {/* Title Field */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">Article Title</label>
              <span className="text-[11px] text-slate-400 font-medium">{title.length}/100 characters</span>
            </div>
            <input 
              type="text" 
              maxLength={100}
              placeholder="Enter comprehensive article header text..." 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 font-medium transition duration-150 focus:outline-hidden focus:bg-white focus:ring-1 focus:ring-indigo-600 focus:border-indigo-600 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* Category Dropdown Selection */}
          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Legal Category</label>
            <select 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg font-medium text-slate-700 transition duration-150 focus:outline-hidden focus:bg-white focus:ring-1 focus:ring-indigo-600 focus:border-indigo-600 text-sm cursor-pointer"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="Constitution">Constitution Amendments</option>
              <option value="Land Act">Land and Property Acts</option>
              <option value="Civic Rights">Civic Space and Rights</option>
              <option value="Judiciary">Judiciary Reports</option>
            </select>
          </div>

          {/* Content Body Markdown Editor */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">Content Body</label>
              <span className="px-2 py-0.5 rounded-sm bg-slate-100 text-slate-500 font-mono text-[9px] font-bold tracking-wider">
                RAW MARKDOWN ENGINE
              </span>
            </div>
            <textarea 
              placeholder="Write text body content utilizing structural markup syntax formatting rules..." 
              rows={12} 
              className="w-full p-4 bg-slate-50 border border-slate-200 rounded-lg font-mono text-sm text-slate-800 placeholder-slate-400 transition duration-150 focus:outline-hidden focus:bg-white focus:ring-1 focus:ring-indigo-600 focus:border-indigo-600 resize-y leading-relaxed"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
              <span>Standard line breaks produce individual paragraph runs.</span>
              <span className="font-medium text-slate-500">{wordCount} words registered</span>
            </div>
          </div>

          {/* Submission Area */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-4">
            <span className="text-xs text-slate-400 max-w-xs leading-snug">
              Draft payloads undergo administrative validation prior to live record database serialization.
            </span>
            <button className="bg-indigo-600 text-white px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-indigo-700 transition-all duration-150 cursor-pointer shadow-xs">
              Submit Draft
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN: Live View Preview */}
        <div className="lg:col-span-5 space-y-4 lg:sticky lg:top-6">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider px-1">
            Live Preview Canvas
          </div>
          
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs min-h-[460px] flex flex-col">
            {title ? (
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight leading-tight mb-3">
                {title}
              </h1>
            ) : (
              <h1 className="text-2xl font-medium text-slate-300 tracking-tight leading-tight mb-3 italic">
                Untitled Document
              </h1>
            )}

            {/* Micro Metadata Metrics */}
            <div className="flex items-center gap-2 text-[10px] font-bold text-indigo-700 bg-indigo-50 w-fit px-2 py-0.5 rounded-xs mb-6 border border-indigo-100 uppercase tracking-wider">
              Category: {category}
            </div>

            {/* Document Render Body Text */}
            <div className="text-slate-800 text-sm sm:text-base leading-relaxed space-y-4 flex-1 border-t border-slate-100 pt-4 font-serif">
              {content ? (
                <p className="whitespace-pre-wrap">{content}</p>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center text-slate-300 py-12">
                  <p className="text-xs font-sans italic max-w-xs">
                    Awaiting manuscript inputs to generate public document presentation fields.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
