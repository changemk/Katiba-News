import React, { useState } from 'react';

export const BlogView: React.FC = () => {
  const [comment, setComment] = useState('');
  const [liked, setLiked] = useState(false);

  return (
    <div className="max-w-3xl mx-auto my-8 px-4 sm:px-6 font-sans">
      
      {/* Platform Category Tagline Line */}
      <div className="mb-4 text-[10px] font-bold tracking-widest text-emerald-700 uppercase">
        Public Discussion Forum / Citizen Voice
      </div>

      {/* Main Blog Entry Post Card Container */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs p-6 sm:p-8">
        
        {/* Blog Main Article Body */}
        <div className="border-b border-slate-100 pb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight leading-snug">
            Community Opinion: Enhancing Civic Space
          </h1>
          
          <div className="flex items-center gap-2 mt-3 text-xs text-slate-400">
            <span className="font-semibold text-slate-700">Community Contributor</span>
            <span>•</span>
            <span>September 21, 2026</span>
          </div>

          <p className="text-slate-700 mt-5 leading-relaxed text-sm sm:text-base font-serif">
            The structural dynamics of local public participation require clear, open dialogue channels across decentralized frameworks. Without unified communication parameters, localized policy assessments isolate civic contributions from actual administrative legislative processes...
          </p>
        </div>
        
        {/* Interactive Engagement Panel (Pure Typography States) */}
        <div className="flex items-center gap-8 py-4 text-xs font-bold uppercase tracking-wider border-b border-slate-100">
          
          {/* Like Interaction Toggle Button */}
          <button 
            onClick={() => setLiked(!liked)}
            className={`transition-colors duration-150 cursor-pointer ${
              liked ? 'text-rose-600' : 'text-slate-500 hover:text-rose-600'
            }`}
          >
            <span className="mr-1">{liked ? 'Liked' : 'Like'}</span>
            <span className="font-mono text-[11px]">({liked ? '1' : '0'})</span>
          </button>

          {/* Comment Quantity Metrics Display */}
          <div className="text-slate-500 flex items-center">
            <span className="mr-1">Comments</span>
            <span className="font-mono text-[11px] text-slate-400">(0)</span>
          </div>

        </div>

        {/* Interactive Input Comment Section */}
        <div className="mt-6 space-y-3">
          <div className="flex justify-between items-center">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Join the Dialogue
            </label>
            <span className="text-[11px] text-slate-400">Please observe community safety rules</span>
          </div>

          <textarea 
            placeholder="Add your respectful thoughts and policy assessments to this public civic thread..." 
            rows={3}
            className="w-full p-4 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 text-sm transition duration-150 focus:outline-hidden focus:bg-white focus:ring-1 focus:ring-emerald-600 focus:border-emerald-600 shadow-xs resize-none"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />

          <div className="flex items-center justify-between gap-4 pt-1">
            <span className="text-[11px] text-slate-400 leading-snug max-w-md">
              Submissions post instantly to the public ledger under your registered platform username credentials.
            </span>
            <button className="bg-emerald-700 text-white px-5 py-2.5 rounded-lg font-semibold text-xs uppercase tracking-wider hover:bg-emerald-800 transition-all duration-150 cursor-pointer shadow-xs whitespace-nowrap">
              Post Comment
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
