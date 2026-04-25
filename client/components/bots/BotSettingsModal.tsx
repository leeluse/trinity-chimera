'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, 
  ChevronDown, 
  Bot, 
  Activity, 
  TrendingUp, 
  Coins, 
  Clock, 
  Wallet,
  ShieldCheck,
  Scale,
  Zap,
  Settings2,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { createBot, BotConfig } from '@/lib/api';

interface BotSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  strategies: Array<{ id: string; name: string }>;
  onBotCreated?: () => void;
}

const RISK_PROFILES = {
  conservative: {
    max_position_pct: 5,
    stop_loss_pct: 2,
    take_profit_pct: 5,
    icon: ShieldCheck,
    color: 'from-emerald-500/20 to-teal-500/20',
    borderColor: 'border-emerald-500/50',
    textColor: 'text-emerald-400',
    shadow: 'shadow-[0_0_20px_rgba(16,185,129,0.15)]'
  },
  moderate: {
    max_position_pct: 10,
    stop_loss_pct: 3,
    take_profit_pct: 8,
    icon: Scale,
    color: 'from-indigo-500/20 to-blue-500/20',
    borderColor: 'border-indigo-500/50',
    textColor: 'text-indigo-400',
    shadow: 'shadow-[0_0_20px_rgba(99,102,241,0.15)]'
  },
  aggressive: {
    max_position_pct: 15,
    stop_loss_pct: 5,
    take_profit_pct: 12,
    icon: Zap,
    color: 'from-rose-500/20 to-pink-500/20',
    borderColor: 'border-rose-500/50',
    textColor: 'text-rose-400',
    shadow: 'shadow-[0_0_20px_rgba(244,63,94,0.15)]'
  },
};

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'];
const TIMEFRAMES = ['15m', '1h', '4h', '1d'];

export function BotSettingsModal({ isOpen, onClose, strategies, onBotCreated }: BotSettingsModalProps) {
  const [name, setName] = useState('');
  const [selectedStrategy, setSelectedStrategy] = useState(strategies[0]?.id || '');
  const [leverage, setLeverage] = useState(1);
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [initialCapital, setInitialCapital] = useState(10000);
  const [riskProfile, setRiskProfile] = useState<'conservative' | 'moderate' | 'aggressive'>('moderate');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
 
  useEffect(() => {
    if (strategies.length > 0 && !selectedStrategy) {
      setSelectedStrategy(strategies[0].id);
    }
  }, [strategies, selectedStrategy]);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSuccess(false);
    }
  }, [isOpen]);

  const profileSettings = RISK_PROFILES[riskProfile];

  const handleCreate = async () => {
    if (!name || !selectedStrategy) {
      setError('봇 이름과 전략을 선택해주세요.');
      return;
    }

    setError(null);
    setIsLoading(true);
    
    try {
      const config: BotConfig = {
        name,
        strategy_id: selectedStrategy,
        leverage,
        symbol,
        timeframe,
        initial_capital: initialCapital,
        max_position_pct: profileSettings.max_position_pct,
        stop_loss_pct: profileSettings.stop_loss_pct,
        take_profit_pct: profileSettings.take_profit_pct,
        risk_profile: riskProfile,
      };

      const result = await createBot(config);
      
      if (result.success || result.id) {
        setSuccess(true);
        setTimeout(() => {
          onBotCreated?.();
          onClose();
          setName('');
          setSuccess(false);
        }, 1500);
      } else {
        setError(result.detail || '봇 생성에 실패했습니다.');
      }
    } catch (error: any) {
      setError(error.message || '봇 생성 중 문제가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-slate-950/60 backdrop-blur-md transition-opacity animate-in fade-in duration-300"
        onClick={!isLoading && !success ? onClose : undefined}
      />

      <div className="relative w-full max-w-xl max-h-[85vh] bg-slate-900 border border-slate-700/50 rounded-2xl shadow-2xl flex flex-col animate-in zoom-in-95 duration-300 overflow-hidden">
        
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-indigo-500/50 to-transparent" />
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm z-10 text-white">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-indigo-500/20 rounded-lg border border-indigo-500/30 font-bold">
              <Bot className="w-5 h-5 text-indigo-400" />
            </div>
            <div className="flex flex-col">
              <h2 className="text-sm font-bold tracking-tight">새 트레이딩 봇 생성</h2>
              <p className="text-[10px] text-slate-400 font-medium mt-0.5">전략과 리스크를 설정하여 자동 매매를 시작하세요</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading || success}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-all"
          >
            <X size={18} />
          </button>
        </div>

        <div className="relative flex-1 overflow-y-auto p-5 pb-6 flex flex-col gap-4 custom-scrollbar z-10">
          
          {error && (
            <div className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] font-medium animate-in slide-in-from-top-2">
              <AlertCircle size={14} />
              <p>{error}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 ml-1">봇 이름</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Bot size={13} />
                </div>
                <input
                  type="text"
                  placeholder="예: My Alpha Bot"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-slate-950/50 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:border-indigo-500/50 outline-none transition-all"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 ml-1">전략 선택</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Activity size={13} />
                </div>
                <select
                  value={selectedStrategy}
                  onChange={(e) => setSelectedStrategy(e.target.value)}
                  className="w-full pl-9 pr-9 py-2 bg-slate-950/50 border border-slate-800 rounded-xl text-sm text-slate-200 focus:border-indigo-500/50 outline-none transition-all appearance-none cursor-pointer"
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id} className="bg-slate-900 text-slate-200">
                      {s.name}
                    </option>
                  ))}
                </select>
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-500">
                  <ChevronDown size={13} />
                </div>
              </div>
            </div>
          </div>

          <div className="h-px bg-slate-800/30 w-full my-1" />

          {/* 기본 설정 - 1열 가로로 배치 (4 columns) */}
          <div className="flex flex-col gap-3">
            <h3 className="text-[11px] font-bold text-slate-200 flex items-center gap-2">
              <Settings2 size={13} className="text-indigo-400" />
              기본 설정
            </h3>
            
            <div className="grid grid-cols-4 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-400 ml-1">거래 쌍</label>
                <div className="relative">
                  <select
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-xl text-[12px] text-slate-200 focus:border-indigo-500/50 outline-none transition-all appearance-none cursor-pointer"
                  >
                    {SYMBOLS.map((s) => (
                      <option key={s} value={s} className="bg-slate-900">{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-400 ml-1">타임프레임</label>
                <div className="relative">
                  <select
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-xl text-[12px] text-slate-200 focus:border-indigo-500/50 outline-none transition-all appearance-none cursor-pointer"
                  >
                    {TIMEFRAMES.map((t) => (
                      <option key={t} value={t} className="bg-slate-900">{t}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-400 ml-1">자본금 (USDT)</label>
                <input
                  type="number"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-xl text-[12px] text-slate-200 focus:border-indigo-500/50 outline-none transition-all"
                />
              </div>

              <div className="flex flex-col gap-1">
                <div className="flex justify-between items-center ml-1">
                  <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">레버리지</label>
                  <span className="text-[9px] font-bold text-indigo-400">{leverage.toFixed(1)}x</span>
                </div>
                <div className="relative flex items-center bg-slate-950/50 border border-slate-800 rounded-xl px-2 py-2 h-[34px]">
                  <input
                    type="range"
                    min="1"
                    max="20"
                    step="0.5"
                    value={leverage}
                    onChange={(e) => setLeverage(parseFloat(e.target.value))}
                    className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="h-px bg-slate-800/30 w-full my-1" />

          {/* 리스크 프로파일 */}
          <div className="flex flex-col gap-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 ml-1">리스크 프로파일 전략</label>
            <div className="grid grid-cols-3 gap-3">
              {(Object.keys(RISK_PROFILES) as Array<keyof typeof RISK_PROFILES>).map((profile) => {
                const isSelected = riskProfile === profile;
                const config = RISK_PROFILES[profile];
                const Icon = config.icon;
                
                return (
                  <button
                    key={profile}
                    onClick={() => setRiskProfile(profile)}
                    className={`relative p-2.5 rounded-xl border transition-all duration-300 text-left overflow-hidden group ${
                      isSelected
                        ? `bg-gradient-to-br ${config.color} ${config.borderColor} ${config.shadow}`
                        : 'bg-slate-950/30 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700'
                    }`}
                  >
                    <div className="relative z-10 flex flex-col sm:flex-row items-center sm:items-start gap-2">
                      <div className={`p-1.5 rounded-lg bg-slate-900/80 border ${isSelected ? config.borderColor : 'border-slate-800'} shrink-0`}>
                        <Icon size={14} className={isSelected ? config.textColor : 'text-slate-400'} />
                      </div>
                      <div className="min-w-0">
                        <div className={`text-[11px] font-bold tracking-wide truncate ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                          {profile === 'conservative' && '보수적'}
                          {profile === 'moderate' && '중간'}
                          {profile === 'aggressive' && '공격적'}
                        </div>
                        <div className="text-[9px] text-slate-400 mt-0.5 font-bold leading-tight">
                          {config.max_position_pct}% / {config.stop_loss_pct}%
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 고급 설정 */}
          <div className="bg-slate-950/30 border border-slate-800/80 rounded-xl overflow-hidden mt-1">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between w-full p-2 hover:bg-slate-800/30 transition-colors"
            >
              <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-300">
                <Settings2 size={13} className="text-slate-500" />
                세부 리스크 수치 확인 (고급)
              </div>
              <ChevronDown 
                size={13} 
                className={`text-slate-500 transition-transform duration-300 ${showAdvanced ? 'rotate-180' : ''}`} 
              />
            </button>

            {showAdvanced && (
              <div className="p-3 grid grid-cols-3 gap-3 bg-slate-900/30 border-t border-slate-800/50 animate-in fade-in slide-in-from-top-1 duration-300">
                <div className="flex flex-col gap-1">
                  <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-500 ml-1">최대 비중</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={profileSettings.max_position_pct}
                      className="w-full bg-slate-950 border border-slate-800 text-slate-400 rounded-lg p-2 text-[10px] outline-none cursor-not-allowed"
                      disabled
                    />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[8px] text-slate-500 font-bold">%</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-500 ml-1">자동 손절</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={profileSettings.stop_loss_pct}
                      className="w-full bg-slate-950 border border-slate-800 text-slate-400 rounded-lg p-2 text-[10px] outline-none cursor-not-allowed"
                      disabled
                    />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[8px] text-slate-500 font-bold">%</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[9px] font-semibold uppercase tracking-wider text-slate-500 ml-1">목표 수익률</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={profileSettings.take_profit_pct}
                      className="w-full bg-slate-950 border border-slate-800 text-slate-400 rounded-lg p-2 text-[10px] outline-none cursor-not-allowed"
                      disabled
                    />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[8px] text-slate-500 font-bold">%</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="p-4 border-t border-slate-800 bg-slate-900/80 backdrop-blur-md z-10">
          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={isLoading || success}
              className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all text-[12px] font-bold w-1/4"
            >
              취소
            </button>
            <button
              onClick={handleCreate}
              disabled={isLoading || success}
              className="relative flex-1 group overflow-hidden rounded-xl bg-indigo-600 text-white font-bold text-[12px] transition-all disabled:opacity-70"
            >
              <div className="relative flex items-center justify-center gap-2 h-full py-2">
                {isLoading ? (
                  <>
                    <svg className="animate-spin h-3 w-3 text-white" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    생성 중...
                  </>
                ) : success ? (
                  <>
                    <CheckCircle2 size={14} />
                    완료!
                  </>
                ) : (
                  <>
                    <Bot size={14} />
                    봇 생성하기
                  </>
                )}
              </div>
            </button>
          </div>
        </div>
      </div>
      
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 5px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: #334155;
          border-radius: 20px;
        }
        .custom-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: #334155 transparent;
        }
      `}} />
    </div>
  );
}