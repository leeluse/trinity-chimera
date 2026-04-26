"use client";

import { ReactNode, useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Settings2, Bot } from "lucide-react";
import ModelSettingsModal from "../dashboard/ModelSettingsModal";
import { BotSettingsModal } from "../bots/BotSettingsModal";
import BotList from "../bots/BotList";
import { useModalStore } from "@/store/useModalStore";
import { fetchStrategies } from "@/lib/api";

interface PageHeaderProps {
  statusText?: string;
  statusColor?: string;
  isLoading?: boolean;
  extra?: ReactNode;
}

export const PageHeader = ({
  statusText = "System Live",
  statusColor = "green",
  isLoading = false,
  extra
}: PageHeaderProps) => {
  const pathname = usePathname();
  const isDashboard = pathname === "/";
  const openSettings = useModalStore(state => state.open);
  const [isBotModalOpen, setIsBotModalOpen] = useState(false);
  const [botRefreshTrigger, setBotRefreshTrigger] = useState(0);
  const [strategies, setStrategies] = useState<Array<{ id: string; name: string }>>([]);

  useEffect(() => {
    const loadStrategies = async () => {
      try {
        const data = await fetchStrategies();
        if (Array.isArray(data)) {
          setStrategies(data.map(s => ({ 
            id: s.id || s.key, 
            name: s.label || s.key 
          })));
        }
      } catch (error) {
        console.error('Failed to load strategies:', error);
      }
    };
    loadStrategies();
  }, []);

  const isGreen = statusColor === "green";
  const isBlue = statusColor === "blue";

  const getStatusStyles = () => {
    if (isGreen) return "bg-green-500/10 border-green-500/20 text-green-400 shadow-[0_0_8px_rgba(74,222,128,0.1)]";
    if (isBlue) return "bg-purple-500/10 border-purple-500/30 text-[#bd93f9] shadow-[0_0_10px_rgba(189,147,249,0.2)]";
    return "bg-slate-500/10 border-slate-500/20 text-slate-400";
  };

  const getDotStyles = () => {
    if (isGreen) return "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)]";
    if (isBlue) return "bg-[#bd93f9] shadow-[0_0_10px_rgba(189,147,249,0.7)]";
    return "bg-slate-400";
  };

  return (
    <>
      <header className="flex items-center justify-between px-4 md:px-8 py-3 md:py-4 border-b border-white/[0.05] bg-background backdrop-blur-2xl sticky top-0 z-[100] shadow-2xl">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="relative w-9 h-9 flex items-center justify-center">
              <div className="absolute inset-0 bg-gradient-to-tr from-[#6366f1] via-[#8b5cf6] to-[#ec4899] rounded-lg rotate-45 blur-[8px] opacity-40 animate-pulse"></div>
              <div className="relative w-full h-full bg-background border border-white/20 rounded-lg rotate-45 flex items-center justify-center overflow-hidden">
                <div className="rotate-[-45deg] flex items-center justify-center">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 12L12 22L22 12L12 2ZM12 6L18 12L12 18L6 12L12 6Z" fill="white" fillOpacity="0.9" />
                    <rect x="11" y="11" width="2" height="2" fill="white" />
                  </svg>
                </div>
              </div>
            </div>
            <div className="flex flex-col pl-2">
              <span className="text-lg font-black text-white tracking-[-0.02em] leading-tight">TRINITY<span className="text-[#8b5cf6]">CHIMERA</span></span>
              <div className="flex items-center gap-2">
                <span className="text-[9px] font-bold text-slate-500 tracking-[0.3em] uppercase leading-none">V2.4 Terminal</span>
                <div className="h-[1px] w-4 bg-slate-800"></div>
              </div>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {extra}

          {isDashboard && (
            <>
              <Link
                href="/scanner"
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:bg-white/10 hover:text-cyan-400 hover:border-cyan-500/50 transition-all text-[11px] font-mono font-semibold tracking-wide"
                title="Solo Scanner"
              >
                <span className="text-cyan-500">📡</span>
                <span>SCANNER</span>
              </Link>

              <Link
                href="/liquidation"
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:bg-white/10 hover:text-orange-400 hover:border-orange-500/50 transition-all text-[11px] font-mono font-semibold tracking-wide"
                title="청산 압력 지도"
              >
                <span className="text-orange-500">🔥</span>
                <span>LIQ MAP</span>
              </Link>

              <div className={`flex items-center gap-2 px-3 py-1 rounded-full border transition-all duration-300 ${getStatusStyles()}`}>
                <div className={`w-1.5 h-1.5 rounded-full animate-pulse ${getDotStyles()}`}></div>
                <span className="text-[10px] font-bold uppercase tracking-wider">
                  {isLoading ? '로딩 중...' : statusText}
                </span>
              </div>
            </>
          )}

          <button
            onClick={() => setIsBotModalOpen(true)}
            className="p-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:bg-white/10 hover:text-white hover:border-purple-500/50 transition-all group"
            title="봇 설정"
          >
            <Bot size={18} className="group-hover:rotate-12 transition-transform duration-500" />
          </button>

          <button
            onClick={openSettings}
            className="p-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:bg-white/10 hover:text-white hover:border-blue-500/50 transition-all group"
            title="모델 엔진 설정"
          >
            <Settings2 size={18} className="group-hover:rotate-45 transition-transform duration-500" />
          </button>
        </div>
      </header>

      {/* Bot Settings Modal */}
      <BotSettingsModal
        isOpen={isBotModalOpen}
        onClose={() => setIsBotModalOpen(false)}
        strategies={strategies}
        onBotCreated={() => setBotRefreshTrigger(prev => prev + 1)}
      />

      {/* Model Settings Modal */}
      <ModelSettingsModal />
    </>
  );
};

export default PageHeader;
