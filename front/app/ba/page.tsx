'use client';

import React, { useState } from 'react';
import { 
  BarChart3, 
  TrendingUp, 
  Target, 
  Zap, 
  Activity, 
  ChevronDown, 
  Calendar, 
  Play, 
  Send, 
  Share2, 
  Save, 
  Copy, 
  CheckCircle2, 
  Search,
  Settings,
  MoreHorizontal,
  RefreshCw,
  Layout,
  Plus,
  CandlestickChart,
  Grid3X3,
  Maximize2,
  FileText,
  ArrowUpRight,
  ArrowDownRight,
  MousePointer2,
  Edit2,
  Type,
  Eye,
  LineChart
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function BacktestAnalysisPage() {
  const [activeTab, setActiveTab] = useState('지표');

  // Premium Obsidian Tokens (Muted & Professional)
  const ACCENT = '#3b82f6'; // Professional Blue
  const SUCCESS = '#10b981';
  const DANGER = '#f43f5e';
  const BG_MAIN = '#030408';
  const BG_CARD = 'rgba(15, 17, 26, 0.4)';
  const BORDER = 'rgba(255, 255, 255, 0.04)';

  const priceData = {
    labels: Array.from({ length: 80 }).map((_, i) => i),
    datasets: [{
      data: Array.from({ length: 80 }).map((_, i) => 70000 + (Math.sin(i * 0.12) * 2000) + (i * 100)),
      borderColor: ACCENT, borderWidth: 1.5, pointRadius: 0, tension: 0.1, fill: false,
    }]
  };

  const equityData = {
    labels: Array.from({ length: 120 }).map((_, i) => i),
    datasets: [
      { 
        label: 'Equity', 
        data: Array.from({ length: 120 }).map((_, i) => 8000 + (i * 90) + (Math.sin(i * 0.15) * 500)), 
        borderColor: ACCENT, 
        backgroundColor: 'rgba(59, 130, 246, 0.03)', 
        borderWidth: 2, 
        pointRadius: 0, 
        fill: true, 
        tension: 0.4 
      },
      { 
        label: 'Bench', 
        data: Array.from({ length: 120 }).map((_, i) => 8000 + (i * 20) + (Math.cos(i * 0.1) * 300)), 
        borderColor: 'rgba(255, 255, 255, 0.08)', 
        borderWidth: 1, 
        borderDash: [4, 4], 
        pointRadius: 0, 
        tension: 0.3 
      }
    ]
  };

  return (
    <div className="min-h-screen bg-[#030408] text-[#e2e8f0] font-sans flex flex-col overflow-hidden selection:bg-blue-500/30 tracking-tight">
      
      {/* 1. MINIMALIST TOP BAR (CLEAN & SHARP) */}
      <div className="h-11 border-bottom border-white/[0.03] bg-[#030408] flex items-center justify-between px-3 shrink-0">
        <div className="flex items-center space-x-1">
           <button className="p-2 hover:bg-white/5 rounded-md text-blue-500 transition-colors"><MousePointer2 size={14}/></button>
           <div className="h-4 w-px bg-white/10 mx-2" />
           <button className="p-2 hover:bg-white/5 rounded-md text-slate-500 hover:text-slate-200 transition-colors"><TrendingUp size={15} /></button>
           <button className="p-2 hover:bg-white/5 rounded-md text-slate-500 hover:text-slate-200 transition-colors"><BarChart3 size={15} /></button>
           <button className="p-2 hover:bg-white/5 rounded-md text-slate-500 hover:text-slate-200 transition-colors"><Grid3X3 size={15} /></button>
           <div className="h-4 w-px bg-white/10 mx-2" />
           <button className="flex items-center space-x-2 px-3 py-1.5 hover:bg-white/5 rounded-md text-slate-400 border border-white/5 mx-1 transition-all">
              <CandlestickChart size={14}/> <span className="text-[11px] font-semibold uppercase tracking-wider">Indicators</span> <ChevronDown size={12}/>
           </button>
           <div className="h-4 w-px bg-white/10 mx-4" />
           <span className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.4em]">BTC/USDT · 1h · HYPERLIQUID</span>
        </div>
        <div className="flex items-center space-x-4">
           <div className="flex items-center space-x-1.5 opacity-60">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
              <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">LIVE SYNC</span>
           </div>
           <div className="h-4 w-px bg-white/10" />
           <button className="text-slate-500 hover:text-white transition-colors"><Settings size={16}/></button>
           <div className="flex -space-x-1">
              {[1,2].map(i => (
                <div key={i} className="w-6 h-6 rounded-full border border-[#030408] bg-slate-800 shadow-xl overflow-hidden ring-1 ring-white/5">
                   <img src={`https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${i+100}`} alt="av" className="w-full h-full opacity-60" />
                </div>
              ))}
           </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        
        {/* MAIN TERMINAL ENGINE */}
        <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col p-6 space-y-6 bg-[#030408]">
           
           {/* 2. PRICE CHART AREA (PRECISION VISUAL) */}
           <div className="w-full h-[380px] bg-[#05060b] border border-white/[0.03] rounded-3xl relative shadow-[0_30px_60px_-15px_rgba(0,0,0,0.5)] overflow-hidden group">
              {/* Grid texture for "Premium" feel */}
              <div className="absolute inset-0 opacity-[0.02] pointer-events-none" 
                   style={{ backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
              
              {/* Right Scale */}
              <div className="absolute top-10 right-6 z-10 flex flex-col space-y-4">
                 {['100,000.00', '90,000.00', '80,000.00', '70,054.76', '60,000.00'].map((p, i) => (
                    <span key={i} className={`text-[10px] font-mono text-right ${p.includes('.') && !p.endsWith('.00') ? 'bg-blue-600/90 text-white px-2 py-0.5 rounded-sm' : 'text-slate-600'}`}>{p}</span>
                 ))}
              </div>

              <div className="absolute inset-0 px-4 pt-16 pb-6">
                 <Line data={priceData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } }} />
              </div>

              {/* Minimalist Markers */}
              <div className="absolute top-20 left-40">
                 <div className="w-4 h-4 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center text-[8px] font-black text-red-500">X</div>
                 <div className="w-px h-10 bg-gradient-to-b from-red-500/20 to-transparent mx-auto" />
              </div>
           </div>

           {/* 3. STRATEGY BAR (RICH OBSIDIAN STYLE) */}
           <div className="grid grid-cols-12 gap-4 p-2 bg-white/[0.01] border border-white/[0.03] rounded-2xl shadow-xl">
              <div className="col-span-3 flex items-center bg-[#0a0b12] border border-white/5 rounded-xl px-4 py-2.5 cursor-pointer hover:border-blue-500/40 transition-all group">
                 <Layout size={14} className="text-blue-500 mr-3" />
                 <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest truncate">V1 Donchian Breakout ATR</span>
                 <span className="text-[9px] font-black text-green-500 ml-3 px-2 py-0.5 bg-green-500/10 rounded-md">+51.1%</span>
                 <ChevronDown size={14} className="text-slate-700 ml-auto group-hover:text-blue-400 transition-colors" />
              </div>
              <div className="col-span-2 flex items-center bg-[#0a0b12] border border-white/5 rounded-xl px-4 py-2.5 cursor-pointer group">
                 <span className="text-[11px] font-bold text-slate-500 uppercase flex-1 transition-colors group-hover:text-slate-200">BTC</span><ChevronDown size={14} className="text-slate-700" />
              </div>
              <div className="col-span-2 flex items-center bg-[#0a0b12] border border-white/5 rounded-xl px-4 py-2.5 cursor-pointer group">
                 <span className="text-[11px] font-bold text-slate-500 uppercase flex-1 transition-colors group-hover:text-slate-200">1h</span><ChevronDown size={14} className="text-slate-700" />
              </div>
              <div className="col-span-3 flex items-center bg-[#0a0b12] border border-white/5 rounded-xl px-4 py-2.5 space-x-4">
                 <Calendar size={14} className="text-slate-600" />
                 <span className="text-[10px] font-bold text-slate-500 tracking-tighter uppercase">2025. 12. 01. → 2026. 03. 20.</span>
              </div>
              <div className="col-span-2 flex space-x-2">
                 <button className="flex-1 bg-white/5 hover:bg-white/10 border border-white/10 text-white font-bold text-[11px] rounded-xl transition-all uppercase tracking-widest">Backtest</button>
                 <button className="p-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl shadow-[0_10px_20px_-5px_rgba(37,99,235,0.4)] transition-all active:scale-95"><Zap size={14} fill="currentColor"/></button>
              </div>
           </div>

           {/* 4. CLEAN TABS & ACTIONS */}
           <div className="flex items-center justify-between px-2 pt-2 border-t border-white/[0.03]">
              <div className="flex space-x-10">
                 {['코드', '지표', '거래 내역'].map(tab => (
                    <button key={tab} onClick={() => setActiveTab(tab)} className={`text-[12px] font-bold transition-all relative ${activeTab === tab ? 'text-slate-100 pb-3' : 'text-slate-600 hover:text-slate-400 pb-3'}`}>
                      {tab}
                      {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 rounded-full" />}
                    </button>
                 ))}
              </div>
              <div className="flex space-x-8">
                 <button className="flex items-center space-x-2 text-[11px] font-bold text-slate-500 hover:text-blue-400 transition-all"><Save size={13}/> <span>저장</span></button>
                 <button className="flex items-center space-x-2 text-[11px] font-bold text-slate-500 hover:text-blue-400 transition-all"><Copy size={13}/> <span>복사</span></button>
              </div>
           </div>

           {/* 5. SUMMARY ROW (MUTED PREMIUM STYLE) */}
           <div className="grid grid-cols-5 gap-5">
              {[
                { label: '총 수익률', val: '+51.15%', sub: '34 거래 내역', color: 'text-green-400', bg: 'bg-green-400/5', border: 'border-green-400/10' },
                { label: '최대 낙폭', val: '11.67%', sub: 'Safe Range', color: 'text-slate-200', bg: 'bg-white/5', border: 'border-white/5' },
                { label: '승률', val: '52.94%', sub: '18W 16L', color: 'text-slate-200', bg: 'bg-white/5', border: 'border-white/5' },
                { label: '수익 팩터', val: '3.31', sub: 'Calculated', color: 'text-blue-400', bg: 'bg-blue-400/5', border: 'border-blue-400/10' },
                { label: '샤프 비율', val: '3.39', sub: 'High Fidelity', color: 'text-purple-400', bg: 'bg-purple-400/5', border: 'border-purple-400/10' },
              ].map((card, i) => (
                <div key={i} className={`p-6 rounded-[24px] border ${card.border} ${card.bg} shadow-lg transition-all hover:translate-y-[-2px] hover:shadow-2xl cursor-default`}>
                   <p className="text-[10px] font-bold text-slate-500 uppercase mb-4 tracking-[0.2em]">{card.label}</p>
                   <p className={`text-2xl font-black ${card.color} tracking-tighter mb-1.5`}>{card.val}</p>
                   <p className="text-[10px] font-medium text-slate-600 tracking-wide">{card.sub}</p>
                </div>
              ))}
           </div>

           {/* 6. ADVANCED EQUITY CURVE */}
           <div className="p-10 bg-[#05060b] border border-white/[0.03] rounded-[32px] shadow-3xl">
              <div className="flex items-center justify-between mb-12">
                 <h3 className="text-xs font-bold tracking-[0.4em] uppercase text-slate-500">자산 곡선</h3>
                 <div className="flex space-x-10">
                    <div className="flex items-center space-x-3"><div className="w-5 h-1.5 bg-blue-500 rounded-full" /><span className="text-[11px] font-bold text-slate-600 uppercase tracking-widest">자산 곡선</span></div>
                    <div className="flex items-center space-x-3"><div className="w-5 h-1.5 bg-white/10 rounded-full" /><span className="text-[11px] font-bold text-slate-600 uppercase tracking-widest">매수 후 보유</span></div>
                 </div>
              </div>
              <div className="h-[280px]">
                 <Line data={equityData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { position: 'right', grid: { color: 'rgba(255,255,255,0.01)' }, ticks: { font: { size: 10 }, color: '#334155' } } } }} />
              </div>
           </div>

           {/* 7. PERFORMANCE GRIDS (CLEANER REPRODUCTION) */}
           <div className="bg-[#05060b] border border-white/[0.03] rounded-[32px] p-10 shadow-3xl space-y-16">
              <div>
                 <div className="flex items-center space-x-4 mb-10">
                    <h3 className="text-xs font-bold tracking-[0.5em] text-slate-400 uppercase font-mono">성능</h3>
                    <div className="h-px flex-1 bg-white/[0.03]" />
                 </div>
                 <div className="grid grid-cols-2 gap-x-32 gap-y-10">
                    <div className="space-y-6">
                       <span className="text-[11px] font-bold text-slate-600 uppercase tracking-widest inline-block border-b-2 border-blue-500/30 pb-1 mb-2">수익</span>
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">총 수익률</span><span className="text-[13px] font-black text-green-500">+51.15%</span></div>
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">초과 성과</span><span className="text-[13px] font-black text-green-500">+73.62%</span></div>
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">예상 수익</span><span className="text-[13px] font-black text-green-500">$150.44</span></div>
                    </div>
                    <div className="space-y-6">
                       <div className="h-[43px]" />
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">매수 후 보유</span><span className="text-[13px] font-black text-rose-500">-22.47%</span></div>
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">수수료</span><span className="text-[13px] font-black text-slate-400">$368.48</span></div>
                    </div>
                 </div>
                 <div className="mt-14 space-y-6">
                    <span className="text-[11px] font-bold text-slate-600 uppercase tracking-widest inline-block border-b-2 border-blue-500/30 pb-1 mb-2">위험</span>
                    <div className="grid grid-cols-2 gap-x-32 gap-y-6">
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">최대 낙폭</span><span className="text-[13px] font-black text-slate-400">11.67%</span></div>
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">샤프 비율</span><span className="text-[13px] font-black text-blue-400">3.39</span></div>
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">소르티노 비율</span><span className="text-[13px] font-black text-blue-400">3.90</span></div>
                       <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">Calmar 비율</span><span className="text-[13px] font-black text-slate-600">14.68</span></div>
                    </div>
                 </div>
              </div>

              {/* 8. TRADE ANALYSIS (PRECISION VISUAL) */}
              <div className="pt-8">
                 <div className="flex items-center space-x-4 mb-10">
                    <h3 className="text-xs font-bold tracking-[0.5em] text-slate-400 uppercase font-mono">거래 분석</h3>
                    <div className="h-px flex-1 bg-white/[0.03]" />
                 </div>
                 <div className="flex justify-between items-center mb-6">
                    <span className="text-[11px] font-bold text-slate-600 uppercase tracking-widest opacity-60">34 Transactions Total</span>
                    <span className="text-[11px] font-bold text-slate-600 uppercase tracking-widest">Rate of Success <span className="text-green-500 ml-2">+52.94%</span></span>
                 </div>
                 <div className="h-3 w-full bg-rose-500/10 rounded-full flex overflow-hidden mb-12 border border-white/[0.03] shadow-inner shadow-black">
                    <div className="h-full bg-gradient-to-r from-green-600 to-green-500 shadow-[0_0_15px_rgba(34,197,94,0.2)]" style={{ width: '53%' }} />
                 </div>
                 <div className="grid grid-cols-2 gap-x-32 gap-y-6">
                    <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">가장 큰 승리</span><span className="text-[13px] font-black text-green-500">+17.34%</span></div>
                    <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">최대 손실</span><span className="text-[13px] font-black text-rose-500">-4.38%</span></div>
                    <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">평균 수익</span><span className="text-[13px] font-black text-green-500">+3.53%</span></div>
                    <div className="flex justify-between items-center group"><span className="text-[13px] font-bold text-slate-500 group-hover:text-slate-300 transition-colors">평균 손실</span><span className="text-[13px] font-black text-rose-500">-1.14%</span></div>
                    <div className="flex justify-between items-center group border-t border-white/5 pt-6 mt-4"><span className="text-[12px] font-black text-slate-600 uppercase tracking-[0.2em]">최대 연속 승리</span><span className="text-[20px] font-black text-green-500 font-mono tracking-widest">3</span></div>
                    <div className="flex justify-between items-center border-t border-white/5 pt-6 mt-4"><span className="text-[12px] font-black text-slate-600 uppercase tracking-[0.2em]">최대 연속 손실 횟수</span><span className="text-[20px] font-black text-rose-500 font-mono tracking-widest">4</span></div>
                 </div>
              </div>
           </div>
           
           <div className="h-20" />
        </div>

        {/* ── RIGHT ANALYTICS SIDEBAR (REFINED) ── */}
        <div className="w-[480px] bg-[#030408] border-l border-white/[0.03] flex flex-col p-12 space-y-16 shrink-0 shadow-[-20px_0_40px_rgba(0,0,0,0.5)]">
           <div>
              <div className="flex items-center space-x-4 mb-14">
                 <Activity size={24} className="text-blue-500 animate-pulse" />
                 <div className="flex flex-col">
                    <span className="text-[12px] font-bold tracking-[0.6em] text-slate-700 uppercase">Analysis Kit</span>
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1 opacity-50">Realtime Insight Engine</span>
                 </div>
              </div>
              <div className="space-y-6">
                 <div className="p-8 rounded-[32px] bg-white/[0.01] border border-white/5 flex items-start space-x-6 hover:bg-white/[0.03] transition-all cursor-default">
                    <CheckCircle2 size={24} className="text-green-500 mt-1 shrink-0" />
                    <div>
                       <span className="text-[12px] font-bold text-slate-200 uppercase tracking-widest">전략 생성 보고</span>
                       <p className="text-[12px] text-slate-500 mt-3 leading-relaxed font-medium">Donchian Breakout ATR (Relaxed) 생성되었습니다.</p>
                       <button className="mt-6 px-5 py-2 bg-white/5 rounded-2xl text-[10px] font-bold text-slate-400 hover:bg-white/10 transition-all uppercase tracking-widest shadow-xl">Source Code</button>
                    </div>
                 </div>
                 <div className="p-8 rounded-[32px] bg-white/[0.01] border border-white/5 flex items-start space-x-6 shadow-2xl">
                    <CheckCircle2 size={24} className="text-blue-500 mt-1 shrink-0" />
                    <div className="flex flex-col w-full">
                       <span className="text-[12px] font-bold text-slate-200 uppercase tracking-widest">백테스트 결과 검증</span>
                       <div className="mt-6 flex space-x-6">
                          <div className="flex-1 bg-white/5 p-4 rounded-2xl border border-white/5 flex flex-col items-center">
                             <p className="text-[9px] text-slate-600 font-bold uppercase tracking-widest">Validation Return</p>
                             <p className="text-[16px] font-black text-green-500 mt-1">+51.15%</p>
                          </div>
                          <div className="flex-1 bg-white/5 p-4 rounded-2xl border border-white/5 flex flex-col items-center">
                             <p className="text-[9px] text-slate-600 font-bold uppercase tracking-widest">Max Drawdown</p>
                             <p className="text-[16px] font-black text-slate-100 mt-1">11.6%</p>
                          </div>
                       </div>
                    </div>
                 </div>
              </div>
           </div>

           <div className="space-y-12">
              <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-[0.8em] flex items-center space-x-6">전략 설계 <div className="h-px flex-1 bg-white/[0.05]" /></h4>
              <ul className="space-y-8 px-1">
                 {['도치안 채널(ATR 1.5x) 돌파시 진입 최적화.', '횡보 필터: 변동폭이 ATR(14) 미만 체크.', '반전 청산 신호 기반 리스크 자동 제어.', '10배 레버리지 기준 전액 매수 체계.'].map((text, i) => (
                    <li key={i} className="flex space-x-6 items-start group cursor-default"><div className="w-2 h-2 rounded-full bg-blue-600/50 mt-1.5 shrink-0 transition-all group-hover:bg-blue-500 group-hover:scale-150 shadow-blue-500/50" /><p className="text-[13px] text-slate-500 font-medium leading-relaxed group-hover:text-slate-200 transition-all">{text}</p></li>
                 ))}
              </ul>
           </div>

           <div className="space-y-12">
              <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-[0.8em] flex items-center space-x-6">진단 인사이트 <div className="h-px flex-1 bg-white/[0.05]" /></h4>
              <div className="space-y-8 px-1">
                 <div className="flex space-x-6 group cursor-default"><div className="w-2 h-2 rounded-full bg-purple-500/50 mt-1.5 shrink-0" /><p className="text-[13px] text-slate-500 font-medium leading-relaxed group-hover:text-slate-200 transition-all">대부분 반전 신호로 청산되어 손절 비율이 매우 낮음.</p></div>
                 <div className="flex space-x-6 group cursor-default"><div className="w-2 h-2 rounded-full bg-purple-500/50 mt-1.5 shrink-0" /><p className="text-[13px] text-slate-500 font-medium leading-relaxed group-hover:text-slate-200 transition-all">트레일링 스탑 적용 시 수익 보존율 14% 향상 기대.</p></div>
              </div>
           </div>

           <div className="flex-1" />
           <div className="relative group">
              <textarea placeholder="Ask anything about strategy design..." className="w-full bg-[#030408] border border-white/[0.1] rounded-[40px] p-8 pb-20 text-xs font-medium focus:outline-none focus:ring-8 focus:ring-blue-500/10 focus:border-blue-500/30 transition-all resize-none shadow-3xl placeholder:text-slate-800" rows={3} />
              <div className="absolute left-8 bottom-8 flex items-center space-x-6 text-slate-700">
                 <button className="hover:text-blue-400 transition-all"><Search size={22} /></button><button className="hover:text-blue-400 transition-all"><FileText size={22} /></button>
              </div>
              <button className="absolute right-6 bottom-6 w-12 h-12 bg-blue-600 text-white rounded-2xl shadow-xl flex items-center justify-center hover:bg-blue-500 transition-all group active:scale-90"><Send size={24} className="group-hover:translate-x-1" /></button>
           </div>
        </div>
      </div>
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.04); border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.08); }
        .tracking-tight { letter-spacing: -0.025em; }
      `}</style>
    </div>
  );
}
