"use client";

import LogCard from "@/components/cards/LogCard";
import { PerformanceRow } from "@/types";

// Extracted Sections
import PanelTabs from "./sections/PanelTabs";
import AgentFilter from "./sections/AgentFilter";
import PerformanceSummary from "./sections/PerformanceSummary";

import { NAMES, COLORS } from "@/constants";

interface DashboardRightPanelProps {
  activeAgent: string;
  setActiveAgent: (name: string) => void;
  names: string[];
}

export default function DashboardRightPanel({
  activeAgent,
  setActiveAgent,
  names
}: DashboardRightPanelProps) {
  const performanceData: PerformanceRow[] = [
    { name: names[0], color: COLORS[0], ret: '+79.72%', sh: '2.41', mdd: '-12.3%', pos: true },
    { name: names[1], color: COLORS[1], ret: '+22.78%', sh: '1.87', mdd: '-8.1%', pos: true },
    { name: names[2], color: COLORS[2], ret: '+15.63%', sh: '1.23', mdd: '-18.9%', pos: true },
    { name: names[3], color: COLORS[3], ret: '-4.06%', sh: '-0.31', mdd: '-24.7%', pos: false },
  ];

  const agentIds = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent'];

  const logsData = [
    {
      agentId: 'momentum_hunter',
      agentName: names[0],
      avatar: (names[0] || "M").charAt(0),
      avatarBg: "rgba(56,189,248,0.1)",
      color: "var(--agent-1)",
      time: "04/06 · 15:00",
      analysis: "BTC가 범위 제한 국면에 진입했습니다. <span class='text-white font-medium'>$64,191 ~ $69,540</span> 사이에서 진동 중이며, 이는 횡보 구간임을 시사합니다. Donchian 채널 돌파 필터(ATR 2.0×)를 통과하여 <span class='text-white font-medium'>그리드 전략(41레벨)</span> 을 배포합니다.",
      reason: "이전 추세추종 전략이 연속 3회 손절 후 <span class='text-white font-medium'>샤프지수 1.12 → 2.41로 개선</span> 이 필요했습니다. 백테스트 결과 횡보 구간에서 평균복귀 전략 수익률이 38% 높았습니다.",
      params: [
        { name: "donchian_len", oldVal: "20", newVal: "15", trend: "neutral" as const },
        { name: "atr_mult", oldVal: "1.5", newVal: "2.0", trend: "up" as const },
        { name: "sl_atr", oldVal: "1.5×", newVal: "2.0×", trend: "neutral" as const },
        { name: "tp_atr", oldVal: "3.0×", newVal: "4.0×", trend: "up" as const },
      ]
    },
    {
      agentId: 'momentum_hunter',
      agentName: names[0],
      avatar: (names[0] || "M").charAt(0),
      avatarBg: "rgba(56,189,248,0.1)",
      color: "var(--agent-1)",
      time: "04/06 · 13:15",
      analysis: "시장 국면이 전환되었습니다. <span class='text-white font-medium'>$64,117 ~ $69,460</span> 범위 구조가 붕괴되었으며(41 그리드 레벨 무력화), 방향성 추세 이동 준비가 필요합니다.",
      reason: "범위 제한→추세 국면 전환으로 현재 그리드 전략의 <span class='text-white font-medium'>예상 손실이 +4.2% 악화</span> 될 것으로 판단, 모든 포지션 정리 후 방향성 전략으로 전환합니다.",
    },
    {
      agentId: 'mean_reverter',
      agentName: names[1],
      avatar: (names[1] || "A").charAt(0),
      avatarBg: "rgba(189,147,249,0.1)",
      color: "var(--agent-2)",
      time: "04/06 · 12:45",
      analysis: "변동성 압축이 감지되었습니다. <span class='text-white font-medium'>Bollinger Band</span> 폭이 최근 72시간 내 최저치로 좁아졌습니다. 상하단 박스권 매매를 위한 <span class='text-white font-medium'>평균 복귀 로직</span>을 활성화합니다.",
      reason: "저변동성 국면에서는 추세 추종 시 잦은 손절이 발생합니다. 현재 델타 중립을 유지하며 <span class='text-white font-medium'>평균 복귀 수익률 12% 목표</span>로 운용합니다."
    }
  ];

  const filteredLogs = (activeAgent === "전체" || activeAgent === "ALL")
    ? logsData
    : logsData.filter(log => log.agentId === activeAgent || log.agentName === activeAgent);

  return (
    <>
      <PanelTabs />
      <AgentFilter names={names} activeAgent={activeAgent} setActiveAgent={setActiveAgent} />

      <div className="flex-1 overflow-y-auto min-h-0 bg-[#060912]/30 no-scrollbar flex flex-col">
        <div className="flex flex-col gap-4 p-4">
          {filteredLogs.map((log, idx) => (
            <LogCard
              key={idx}
              {...log}
              onClick={() => setActiveAgent(log.agentId)}
              isActive={activeAgent === log.agentId}
            />
          ))}
          {filteredLogs.length === 0 && (
            <div className="py-20 text-center opacity-30">
              <p className="text-xs italic">해당 에이전트의 최근 로그가 없습니다.</p>
            </div>
          )}
        </div>
      </div>

      <PerformanceSummary
        performanceData={performanceData}
        activeAgent={activeAgent}
        onAgentClick={(name) => {
          const idx = performanceData.findIndex(row => row.name === name);
          if (idx !== -1) setActiveAgent(agentIds[idx]);
        }}
      />
    </>
  );
}