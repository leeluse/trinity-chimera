'use client';

import React, { useEffect, useState } from 'react';
import { Play, Square, Trash2, Bot as BotIcon, Activity } from 'lucide-react';
import { fetchBots, startBot, stopBot, deleteBot } from '@/lib/api';
import { COLORS } from '@/constants';

interface BotData {
  id: string;
  name: string;
  is_active: boolean;
  strategies: { name: string };
  sim_state?: {
    current_price?: number;
    equity?: number;
    total_return_pct?: number;
    win_rate?: number;
    sharpe_ratio?: number;
    mdd_pct?: number;
    position?: 'long' | 'short' | 'none';
  };
}

interface BotListProps {
  bots: BotData[];
  refreshTrigger?: number;
}

export default function BotList({ bots, refreshTrigger }: BotListProps) {
  const isLoading = false; // Now handled by parent

  useEffect(() => {
    // Parent handles loading now.
  }, [refreshTrigger]);

  const handleStart = async (botId: string) => {
    try {
      const res = await startBot(botId);
      if (res.success) {
        loadBots();
      } else {
        alert(`봇 시작 실패: ${res.error || '알 수 없는 오류'}`);
      }
    } catch (error) {
      alert(`봇 시작 실패: ${error}`);
    }
  };

  const handleStop = async (botId: string) => {
    try {
      const res = await stopBot(botId);
      if (res.success) {
        loadBots();
      } else {
        alert(`봇 중지 실패: ${res.error || '알 수 없는 오류'}`);
      }
    } catch (error) {
      alert(`봇 중지 실패: ${error}`);
    }
  };

  const handleDelete = async (botId: string) => {
    if (!confirm('정말로 이 봇을 삭제하시겠습니까?')) return;
    try {
      const res = await deleteBot(botId);
      if (res.success) {
        loadBots();
      } else {
        alert(`봇 삭제 실패: ${res.error || '알 수 없는 오류'}`);
      }
    } catch (error) {
      alert(`봇 삭제 실패: ${error}`);
    }
  };

  if (isLoading && bots.length === 0) return null;
  if (bots.length === 0) return null;

  return (
    <div className="flex flex-row overflow-x-auto no-scrollbar gap-6 w-full py-6 snap-x">
      {bots.map((bot, idx) => {
        const isPos = (bot.sim_state?.total_return_pct || 0) >= 0;
        const returnPct = bot.sim_state?.total_return_pct || 0;
        const isBnH = bot.name === 'BTC BnH';
        // 8자리 헥사코드 처리 (이미 알파값이 있는 경우를 대비해 7자리만 추출)
        const baseColor = isBnH ? "#64748b" : (COLORS[idx % COLORS.length]?.substring(0, 7) || "#6366f1");
        const brandColor = baseColor;

        return (
          <div
            key={bot.id}
            className={`flex flex-col min-w-[280px] max-w-[300px] shrink-0 snap-start bg-white/[0.03] backdrop-blur-md rounded-2xl border transition-all duration-300`}
            style={{ 
              borderColor: bot.is_active ? `${brandColor}40` : 'rgba(255,255,255,0.08)',
              boxShadow: bot.is_active ? `0 4px 24px -12px ${brandColor}30` : 'none'
            }}
          >
            {/* --- Card Header --- */}
            <div className={`px-4 py-4 border-b flex items-center justify-between ${isBnH ? 'border-white/[0.03]' : 'border-white/[0.05]'}`}>
              <div className="flex items-center gap-3 min-w-0">
                <div 
                  className="p-1.5 rounded-lg shrink-0 border transition-all"
                  style={{ 
                    backgroundColor: bot.is_active ? `${brandColor}10` : 'rgba(255,255,255,0.02)',
                    color: bot.is_active ? brandColor : '#475569',
                    borderColor: bot.is_active ? `${brandColor}20` : 'rgba(255,255,255,0.05)'
                  }}
                >
                  <BotIcon size={16} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <h3 className="text-[14px] font-black text-slate-100 tracking-tight truncate">
                      {bot.name}
                    </h3>
                    <span className={`flex-shrink-0 flex items-center gap-1.5 px-1.5 py-0.5 rounded text-[7px] font-black uppercase tracking-wider`}
                      style={{
                        backgroundColor: (bot.is_active && !isBnH) 
                          ? (bot.sim_state?.position === 'long' ? 'rgba(16,185,129,0.1)' : bot.sim_state?.position === 'short' ? 'rgba(244,63,94,0.1)' : `${brandColor}20`)
                          : 'rgba(255,255,255,0.03)',
                        color: (bot.is_active && !isBnH)
                          ? (bot.sim_state?.position === 'long' ? '#10b981' : bot.sim_state?.position === 'short' ? '#f43f5e' : brandColor)
                          : '#64748b',
                        border: `1px solid ${(bot.is_active && !isBnH) ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.05)'}`
                      }}
                    >
                      {(bot.is_active && !isBnH) && (
                        <span className={`w-1 h-1 rounded-full animate-pulse`}
                          style={{
                            backgroundColor: bot.sim_state?.position === 'long' ? '#10b981' : bot.sim_state?.position === 'short' ? '#f43f5e' : brandColor
                          }}
                        />
                      )}
                      {(!bot.is_active || isBnH) ? (isBnH ? 'BENCHMARK' : 'IDLE') : (bot.sim_state?.position?.toUpperCase() || 'WATCHING')}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 mt-1.5 py-0.5 text-[9px] font-bold text-slate-600 uppercase tracking-tight">
                    <Activity size={10} className="shrink-0" />
                    <span className="truncate max-w-[100px]">{bot.strategies?.name || 'Manual Strategy'}</span>
                  </div>
                </div>
              </div>

              {/* Header Actions */}
              <div className="flex items-center gap-1.5 shrink-0 ml-4">
                {bot.is_active ? (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleStop(bot.id); }}
                    className="p-2 rounded-lg bg-rose-500/5 text-rose-500/60 hover:bg-rose-500/10 hover:text-rose-500 transition-all border border-rose-500/10 active:scale-90"
                    title="중지"
                  >
                    <Square size={13} className="fill-current" />
                  </button>
                ) : (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleStart(bot.id); }}
                    className="p-2 rounded-lg bg-emerald-500/5 text-emerald-500/60 hover:bg-emerald-500/10 hover:text-emerald-500 transition-all border border-emerald-500/10 active:scale-90"
                    title="시작"
                  >
                    <Play size={13} className="fill-current" />
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(bot.id); }}
                  className="p-2 rounded-lg bg-slate-800/30 text-slate-600 hover:bg-rose-500/10 hover:text-rose-500 transition-all border border-transparent hover:border-rose-500/10 active:scale-90"
                  title="삭제"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>

            {/* --- Metrics --- */}
            <div className="px-4 py-2.5 grid grid-cols-5 border-b border-white/[0.05]">
              <div className="flex flex-col">
                <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest leading-tight">Sharpe</div>
                <div className={`text-[11px] font-bold tabular-nums tracking-tighter mt-1 ${(bot.sim_state?.sharpe_ratio || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                  {bot.sim_state?.sharpe_ratio?.toFixed(1) || '0.0'}
                </div>
              </div>

              <div className="flex flex-col">
                <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest leading-tight">MDD</div>
                <div className="text-[11px] font-bold text-rose-400 tabular-nums tracking-tighter mt-1">
                  {bot.sim_state?.mdd_pct ? `-${Math.abs(bot.sim_state.mdd_pct).toFixed(1)}%` : '0.0%'}
                </div>
              </div>

              <div className="flex flex-col">
                <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest leading-tight">Return</div>
                <div className={`text-[11px] font-bold tabular-nums tracking-tighter mt-1 ${isPos ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                  {isPos ? '+' : ''}{returnPct.toFixed(1)}%
                </div>
              </div>

              <div className="flex flex-col">
                <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest leading-tight">Win</div>
                <div className="text-[11px] font-bold text-slate-200 tabular-nums tracking-tighter mt-1">
                  {(bot.sim_state?.win_rate || 0).toFixed(0)}%
                </div>
              </div>

              <div className="flex flex-col">
                <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest leading-tight">Equity</div>
                <div className="text-[11px] font-bold text-slate-200 tabular-nums tracking-tighter mt-1">
                  ${bot.sim_state?.equity?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || '---'}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
