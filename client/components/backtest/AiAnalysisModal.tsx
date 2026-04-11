"use client";

import { FiX } from "react-icons/fi";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AiAnalysisModalProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading: boolean;
  report: string;
}

export const AiAnalysisModal = ({ isOpen, onClose, isLoading, report }: AiAnalysisModalProps) => {
  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-md flex items-center justify-center p-4" 
      onClick={onClose}
    >
      <div 
        className="bg-zinc-900 border border-purple-500/30 rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col" 
        onClick={e => e.stopPropagation()}
      >
        <div className="p-5 border-b border-white/[0.06] flex items-center justify-between">
          <h2 className="text-lg font-bold text-purple-500 uppercase tracking-widest">
            AI Quant Analysis
          </h2>
          <button 
            onClick={onClose} 
            className="p-2 hover:bg-white/[0.06] rounded-lg transition-colors"
          >
            <FiX />
          </button>
        </div>
        <div className="p-6 overflow-y-auto custom-scrollbar">
          {isLoading ? (
            <div className="flex flex-col items-center py-16">
              <div className="w-8 h-8 rounded-full border-2 border-purple-500/30 border-l-purple-500 animate-spin mb-4" />
              <p className="text-purple-500 font-bold text-xs uppercase">Analyzing data...</p>
            </div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AiAnalysisModal;
