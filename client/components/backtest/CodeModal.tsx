"use client";

import { X, Copy, Check, Terminal } from "lucide-react";
import { useState } from "react";
import CodeEditor from "../common/CodeEditor";

interface CodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  strategyName: string;
  code: string;
}

export default function CodeModal({ isOpen, onClose, strategyName, code }: CodeModalProps) {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300"
        onClick={onClose}
      />
      
      {/* Modal Content */}
      <div className="relative w-full max-w-5xl h-[80vh] bg-[#0c1221] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center">
              <Terminal size={18} className="text-blue-400" />
            </div>
            <div>
              <h2 className="text-sm font-black text-white tracking-tight">{strategyName}</h2>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">Strategy Source Logic</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button 
              onClick={handleCopy}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-bold text-slate-400 hover:bg-white/10 hover:text-white transition-all"
            >
              {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
              {copied ? "Copied!" : "Copy Code"}
            </button>
            <button 
              onClick={onClose}
              className="p-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:bg-white/10 hover:text-white transition-all"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Editor Area */}
        <div className="flex-1 overflow-hidden">
          <CodeEditor code={code} />
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/5 bg-white/[0.01] flex items-center justify-between">
          <div className="flex items-center gap-4">
             <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500 uppercase">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                Python 3.10+
             </div>
             <div className="text-[10px] font-bold text-slate-500 uppercase">Async Engine</div>
          </div>
          <p className="text-[10px] text-slate-600 font-medium">Read-only view of strategy implementation</p>
        </div>
      </div>
    </div>
  );
}
