"use client";

import { 
  Download, Share2, Settings2, Wand2, FileSpreadsheet, 
  FileJson, Camera, ExternalLink, RefreshCw, Layers,
  ChevronRight, ArrowRight
} from "lucide-react";

export default function BacktestActionButtons() {
  return (
    <div className="flex flex-wrap items-center gap-2 w-full py-2 bg-transparent">
      {/* Intelligence Actions */}
      <ActionButton label="AI Deep Analysis" icon={<RefreshCw size={14} />} color="purple" />
      <ActionButton label="Optimization" icon={<Settings2 size={14} />} />
      <ActionButton label="View Logic" icon={<Layers size={14} />} />

      <div className="w-px h-6 bg-white/10 mx-2" />

      {/* Export Actions */}
      <ActionButton label="Export CSV" icon={<FileSpreadsheet size={14} />} />
      <ActionButton label="JSON" icon={<FileJson size={14} />} />
      <ActionButton label="Capture" icon={<Camera size={14} />} />

      <div className="w-px h-6 bg-white/10 mx-2" />

      {/* Deployment Actions */}
      <ActionButton label="Deploy" icon={<ExternalLink size={14} />} color="purple" />
      <ActionButton label="Copy link" icon={<Share2 size={14} />} />
      <ActionButton label="Sync info" icon={<ArrowRight size={14} />} />
    </div>
  );
}

function ActionButton({ label, icon, color = "default" }: { label: string, icon: React.ReactNode, color?: "default" | "blue" | "purple" | "emerald" }) {
  const getStyles = () => {
    switch (color) {
      case "blue": return "bg-purple-600/10 text-purple-400 hover:bg-purple-600/20";
      case "purple": return "bg-purple-600/10 text-purple-400 hover:bg-purple-600/20";
      default: return "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white";
    }
  };

  return (
    <button className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 active:scale-[0.95] group ${getStyles()}`}>
      <span className="shrink-0">{icon}</span>
      <span className="text-[11px] font-bold tracking-tight whitespace-nowrap">{label}</span>
    </button>
  );
}
