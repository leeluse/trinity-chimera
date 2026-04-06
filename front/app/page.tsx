"use client";

import { useEffect, useRef, useState } from "react";
import Chart from "chart.js/auto";
import Head from "next/head";

// ─────────────────────────────────────────────────────────
// Trinity Score 합성 지수 공식
// ─────────────────────────────────────────────────────────
const DAYS = 96;
const labels: string[] = [];
const startDate = new Date('2026-01-01');
for (let i = 0; i < DAYS; i++) {
  const d = new Date(startDate);
  d.setDate(d.getDate() + i);
  labels.push(d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }));
}

function simTrinityScore(retDrift, retNoise, sharpeBase, mddFloor) {
  let cumRet = 0, peakRet = 0, mdd = 0;
  return labels.map(() => {
    const dailyRet = retDrift + (Math.random() - 0.46) * retNoise;
    cumRet += dailyRet;
    peakRet = Math.max(peakRet, cumRet);
    if (peakRet > 0) mdd = Math.min(mdd, (cumRet - peakRet) / peakRet);
    const sharpe = sharpeBase + (Math.random() - 0.4) * 0.3;
    const score = (cumRet * 0.40) + (sharpe * 25 * 0.35) + ((1 + Math.max(mdd, mddFloor)) * 100 * 0.25);
    return parseFloat((100 + score).toFixed(2));
  });
}

function simReturn(drift, noise) {
  let v = 0;
  return labels.map(() => { v += drift + (Math.random() - 0.46) * noise; return parseFloat(v.toFixed(2)); });
}

function simSharpe(base, noise) {
  return labels.map(() => parseFloat((base + (Math.random() - 0.4) * noise).toFixed(3)));
}

const metrics = {
  score: [
    simTrinityScore(0.85, 1.2, 2.2, -0.123),
    simTrinityScore(0.25, 0.7, 1.7, -0.081),
    simTrinityScore(0.15, 1.0, 1.1, -0.189),
    simTrinityScore(-0.04, 1.4, -0.2, -0.247),
    simTrinityScore(-0.18, 1.8, 0.3, -0.320),
  ],
  return: [
    simReturn(0.82, 1.1), simReturn(0.24, 0.65),
    simReturn(0.14, 0.95), simReturn(-0.04, 1.3), simReturn(-0.2, 1.7)
  ],
  sharpe: [
    simSharpe(2.2, 0.4), simSharpe(1.8, 0.35),
    simSharpe(1.2, 0.45), simSharpe(-0.25, 0.5), simSharpe(0.3, 0.6)
  ],
  mdd: [
    simReturn(-12, 2), simReturn(-8, 1),
    simReturn(-18, 5), simReturn(-24, 4), simReturn(-35, 6)
  ],
  win: [
    simSharpe(67, 3), simSharpe(71, 2),
    simSharpe(52, 4), simSharpe(44, 3), simSharpe(30, 5)
  ]
} as any;

const COLORS = ['#63b3ed', '#b794f4', '#68d391', '#f6ad55', '#4a5a7a'];
const NAMES = ['MINARA V2', 'ARBITER V1', 'NIM-ALPHA', 'CHIMERA-β', 'BTC BnH'];

function buildDatasets(metric) {
  return metrics[metric].map((data, i) => ({
    label: NAMES[i], data,
    borderColor: COLORS[i],
    backgroundColor: i === 0 ? 'rgba(99,179,237,0.06)' : 'transparent',
    borderWidth: i === 0 ? 2 : (i === 4 ? 1 : 1.5),
    pointRadius: 0, tension: 0.4,
    fill: i === 0,
    borderDash: i === 3 ? [4, 3] : (i === 4 ? [2, 4] : []),
  }));
}

const hintMap = {
  score: '수식: Return×0.4 + Sharpe×25×0.35 + (1+MDD)×100×0.25',
  return: '누적 일별 수익률 (%)',
  sharpe: '롤링 샤프지수 (일간 추정)',
  mdd: '누적 최대 낙폭 (MDD, 매일 갱신)',
  win: '누적 승률 % (일별 롤링)',
};

export default function Dashboard() {
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstance = useRef<Chart | null>(null);
  const [currentMetric, setCurrentMetric] = useState("score");
  const [activeTab, setActiveTab] = useState("strategy");
  const [activeAgent, setActiveAgent] = useState("전체");

  useEffect(() => {
    if (!chartRef.current) return;
    const ctx = chartRef.current.getContext('2d');
    if (!ctx) return;

    chartInstance.current = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets: buildDatasets(currentMetric) },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        animation: { duration: 500, easing: 'easeInOutQuart' },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(14,20,38,0.97)',
            borderColor: 'rgba(255,255,255,0.08)',
            borderWidth: 1,
            titleColor: '#8b9fc6',
            bodyColor: '#f0f4ff',
            padding: 14,
            callbacks: {
              title: items => `📅 ${items[0].label}`,
              label: item => {
                const v = item.raw;
                if (currentMetric === 'score') return `  ${item.dataset.label}: ${Number(v).toFixed(1)} pt`;
                if (currentMetric === 'return') return `  ${item.dataset.label}: ${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`;
                if (currentMetric === 'sharpe') return `  ${item.dataset.label}: ${Number(v).toFixed(3)}`;
                return `  ${item.dataset.label}: ${v}`;
              },
              afterBody: () => currentMetric === 'score'
                ? ['', '  Return×0.4 + Sharpe×25×0.35 + (1+MDD)×100×0.25']
                : []
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.025)' },
            ticks: { color: '#4a5a7a', font: { size: 10, family: 'JetBrains Mono' }, maxTicksLimit: 8 }
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: {
              color: '#4a5a7a',
              font: { size: 10, family: 'JetBrains Mono' },
              callback: v => {
                if (currentMetric === 'score') return Number(v).toFixed(0) + ' pt';
                if (currentMetric === 'return') return (v >= 0 ? '+' : '') + Number(v).toFixed(1) + '%';
                if (currentMetric === 'sharpe') return Number(v).toFixed(2);
                return v;
              }
            }
          }
        }
      }
    });

    return () => {
      if (chartInstance.current) chartInstance.current.destroy();
    };
  }, []);

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.data.datasets = buildDatasets(currentMetric);
      chartInstance.current.update();
    }
  }, [currentMetric]);

  return (
    <>
      <Head>
        <title>Trinity AI Trading Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      </Head>

      <header>
        <div className="header-left">
          <span className="logo">△ TRINITY</span>
          <span className="header-badge">Live</span>
        </div>
        <div className="header-right">
          <div className="flex-gap">
            <div className="status-dot"></div>
            <span className="status-text">4 Agents Running</span>
          </div>
          <div className="timeframe-group">
            <button className="tf-btn">1d</button>
            <button className="tf-btn">1w</button>
            <button className="tf-btn active">1M</button>
            <button className="tf-btn">3M</button>
            <button className="tf-btn">전체</button>
          </div>
        </div>
      </header>

      <div className="main">
        {/* LEFT PANEL */}
        <div className="left-panel">
          <div className="panel-header">
            <span className="panel-title">Agent Performance</span>
          </div>
          {/* Chart Metric Tabs */}
          <div className="chart-tab-row">
            <button className={`chart-tab ${currentMetric === 'score' ? 'active' : ''}`} onClick={() => setCurrentMetric('score')}>Trinity Score</button>
            <button className={`chart-tab ${currentMetric === 'return' ? 'active' : ''}`} onClick={() => setCurrentMetric('return')}>수익률 %</button>
            <button className={`chart-tab ${currentMetric === 'sharpe' ? 'active' : ''}`} onClick={() => setCurrentMetric('sharpe')}>샤프지수</button>
            <button className={`chart-tab ${currentMetric === 'mdd' ? 'active' : ''}`} onClick={() => setCurrentMetric('mdd')}>MDD</button>
            <button className={`chart-tab ${currentMetric === 'win' ? 'active' : ''}`} onClick={() => setCurrentMetric('win')}>Win Rate</button>
            <span id="metricHint" className="metric-hint">{hintMap[currentMetric]}</span>
          </div>

          {/* Agent Stat Cards */}
          <div className="agent-cards">
            <div className="agent-card a1 active">
              <div className="agent-name-row">
                <div className="agent-avatar">M</div>
                <span className="agent-label" style={{ color: 'var(--agent-1)' }}>MINARA V2</span>
              </div>
              <div className="agent-strategy">Donchian Breakout</div>
              <div className="agent-meta">
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Sharpe</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-green)' }}>2.41</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">MDD</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-red)' }}>-12.3%</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Win%</div>
                  <div className="agent-meta-val">67.4%</div>
                </div>
              </div>
            </div>
            <div className="agent-card a2">
              <div className="agent-name-row">
                <div className="agent-avatar">A</div>
                <span className="agent-label" style={{ color: 'var(--agent-2)' }}>ARBITER V1</span>
              </div>
              <div className="agent-strategy">Grid + Mean Rev</div>
              <div className="agent-meta">
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Sharpe</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-green)' }}>1.87</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">MDD</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-red)' }}>-8.1%</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Win%</div>
                  <div className="agent-meta-val">71.2%</div>
                </div>
              </div>
            </div>
            <div className="agent-card a3">
              <div className="agent-name-row">
                <div className="agent-avatar">N</div>
                <span className="agent-label" style={{ color: 'var(--agent-3)' }}>NIM-ALPHA</span>
              </div>
              <div className="agent-strategy">Trend Following</div>
              <div className="agent-meta">
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Sharpe</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-green)' }}>1.23</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">MDD</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-red)' }}>-18.9%</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Win%</div>
                  <div className="agent-meta-val">52.1%</div>
                </div>
              </div>
            </div>
            <div className="agent-card a4">
              <div className="agent-name-row">
                <div className="agent-avatar">C</div>
                <span className="agent-label" style={{ color: 'var(--agent-4)' }}>CHIMERA-β</span>
              </div>
              <div className="agent-strategy">Scalping ATR</div>
              <div className="agent-meta">
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Sharpe</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-red)' }}>-0.31</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">MDD</div>
                  <div className="agent-meta-val" style={{ color: 'var(--accent-red)' }}>-24.7%</div>
                </div>
                <div className="agent-meta-item">
                  <div className="agent-meta-label">Win%</div>
                  <div className="agent-meta-val">44.8%</div>
                </div>
              </div>
            </div>
          </div>

          {/* Main Chart */}
          <div className="chart-area">
            <div className="chart-legend">
              <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--agent-1)' }}></div><span className="legend-label">MINARA V2</span></div>
              <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--agent-2)' }}></div><span className="legend-label">ARBITER V1</span></div>
              <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--agent-3)' }}></div><span className="legend-label">NIM-ALPHA</span></div>
              <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--agent-4)' }}></div><span className="legend-label">CHIMERA-β</span></div>
              <div className="legend-item"><div className="legend-dot" style={{ background: '#4a5a7a', opacity: 0.5 }}></div><span className="legend-label" style={{ opacity: 0.5 }}>BTC BnH</span></div>
            </div>
            <div className="chart-wrap">
              <canvas id="perfChart" ref={chartRef}></canvas>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div className="flex flex-col h-full overflow-hidden h-[calc(100vh-57px)]">
          <div className="right-header shrink-0">
            <div className="tab-row">
              <button className={`tab-btn ${activeTab === 'strategy' ? 'active' : ''}`} onClick={() => setActiveTab('strategy')}>전략 로그</button>
              <button className={`tab-btn ${activeTab === 'params' ? 'active' : ''}`} onClick={() => setActiveTab('params')}>파라미터 변경</button>
              <button className={`tab-btn ${activeTab === 'backtest' ? 'active' : ''}`} onClick={() => setActiveTab('backtest')}>백테스트 요약</button>
              <button className={`tab-btn ${activeTab === 'positions' ? 'active' : ''}`} onClick={() => setActiveTab('positions')}>포지션</button>
            </div>
          </div>

          <div className="agent-selector shrink-0">
            <button className={`agent-chip ${activeAgent === '전체' ? 'active' : ''}`} onClick={() => setActiveAgent('전체')}>전체</button>
            <button className={`agent-chip ${activeAgent === 'MINARA V2' ? 'active' : ''}`} onClick={() => setActiveAgent('MINARA V2')} style={{ color: 'var(--agent-1)' }}>MINARA V2</button>
            <button className={`agent-chip ${activeAgent === 'ARBITER V1' ? 'active' : ''}`} onClick={() => setActiveAgent('ARBITER V1')} style={{ color: 'var(--agent-2)' }}>ARBITER V1</button>
            <button className={`agent-chip ${activeAgent === 'NIM-ALPHA' ? 'active' : ''}`} onClick={() => setActiveAgent('NIM-ALPHA')} style={{ color: 'var(--agent-3)' }}>NIM-ALPHA</button>
            <button className={`agent-chip ${activeAgent === 'CHIMERA-β' ? 'active' : ''}`} onClick={() => setActiveAgent('CHIMERA-β')} style={{ color: 'var(--agent-4)' }}>CHIMERA-β</button>
          </div>

          {/* Strategy Log Feed */}
          <div className="flex-1 overflow-y-auto min-h-0" id="stratFeed">
            <div className="p-4 space-y-3">

            {/* Log Card 1 */}
            <div className="log-card flex-shrink-0">
              <div className="log-card-header">
                <div className="log-agent-info">
                  <div className="log-avatar" style={{ background: 'rgba(99,179,237,0.15)', color: 'var(--agent-1)' }}>M</div>
                  <span className="log-agent-name" style={{ color: 'var(--agent-1)' }}>MINARA V2</span>
                </div>
                <span className="log-time">04/06 · 15:00</span>
              </div>
              <div className="log-card-body">
                <div className="log-section">
                  <div className="log-section-label">📊 시장 분석</div>
                  <div className="log-text">BTC가 범위 제한 국면에 진입했습니다. <span className="log-highlight">$64,191 ~ $69,540</span> 사이에서 진동 중이며, 이는 횡보 구간임을 시사합니다. Donchian 채널 돌파 필터(ATR 2.0×)를 통과하여 <span className="log-highlight">그리드 전략(41레벨)</span>을 배포합니다.</div>
                </div>
                <div className="log-section">
                  <div className="log-section-label">🔄 전략 변경 이유</div>
                  <div className="log-text">이전 추세추종 전략이 연속 3회 손절 후 <span className="log-highlight">샤프지수 1.12 → 2.41로 개선</span>이 필요했습니다. 백테스트 결과 횡보 구간에서 평균복귀 전략 수익률이 38% 높았습니다.</div>
                </div>
                <div className="log-section">
                  <div className="log-section-label">⚙️ 파라미터 변경</div>
                  <div className="param-grid">
                    <div className="param-item">
                      <div className="param-name">donchian_len</div>
                      <div className="param-vals">
                        <span className="param-old">20</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new neutral">15</span>
                      </div>
                    </div>
                    <div className="param-item">
                      <div className="param-name">atr_mult</div>
                      <div className="param-vals">
                        <span className="param-old">1.5</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new up">2.0</span>
                      </div>
                    </div>
                    <div className="param-item">
                      <div className="param-name">sl_atr</div>
                      <div className="param-vals">
                        <span className="param-old">1.5×</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new neutral">2.0×</span>
                      </div>
                    </div>
                    <div className="param-item">
                      <div className="param-name">tp_atr</div>
                      <div className="param-vals">
                        <span className="param-old">3.0×</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new up">4.0×</span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>

            {/* Log Card 2 */}
            <div className="log-card flex-shrink-0">
              <div className="log-card-header">
                <div className="log-agent-info">
                  <div className="log-avatar" style={{ background: 'rgba(99,179,237,0.15)', color: 'var(--agent-1)' }}>M</div>
                  <span className="log-agent-name" style={{ color: 'var(--agent-1)' }}>MINARA V2</span>
                </div>
                <span className="log-time">04/06 · 13:15</span>
              </div>
              <div className="log-card-body">
                <div className="log-section">
                  <div className="log-section-label">📊 시장 분석</div>
                  <div className="log-text">시장 국면이 전환되었습니다. <span className="log-highlight">$64,117 ~ $69,460</span> 범위 구조가 붕괴되었으며(41 그리드 레벨 무력화), 방향성 추세 이동 준비가 필요합니다.</div>
                </div>
                <div className="log-section">
                  <div className="log-section-label">🔄 전략 변경 이유</div>
                  <div className="log-text">범위 제한→추세 국면 전환으로 현재 그리드 전략의 <span className="log-highlight">예상 손실이 +4.2% 악화</span>될 것으로 판단, 모든 포지션 정리 후 방향성 전략으로 전환합니다.</div>
                </div>

              </div>
            </div>

            {/* Log Card 3: ARBITER */}
            <div className="log-card flex-shrink-0">
              <div className="log-card-header">
                <div className="log-agent-info">
                  <div className="log-avatar" style={{ background: 'rgba(183,148,244,0.15)', color: 'var(--agent-2)' }}>A</div>
                  <span className="log-agent-name" style={{ color: 'var(--agent-2)' }}>ARBITER V1</span>
                </div>
                <span className="log-time">04/06 · 11:30</span>
              </div>
              <div className="log-card-body">
                <div className="log-section">
                  <div className="log-section-label">📊 시장 분석</div>
                  <div className="log-text">1H RSI가 <span className="log-highlight">72.3 (과매수)</span>에 도달했습니다. 볼린저 밴드 상단 돌파 후 반전 신호가 감지됩니다. 평균복귀 확률 68% 추정.</div>
                </div>
                <div className="log-section">
                  <div className="log-section-label">⚙️ 파라미터 변경</div>
                  <div className="param-grid">
                    <div className="param-item">
                      <div className="param-name">rsi_ob</div>
                      <div className="param-vals">
                        <span className="param-old">70</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new down">72</span>
                      </div>
                    </div>
                    <div className="param-item">
                      <div className="param-name">grid_levels</div>
                      <div className="param-vals">
                        <span className="param-old">20</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new neutral">15</span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>

            {/* Log Card 4: CHIMERA */}
            <div className="log-card flex-shrink-0">
              <div className="log-card-header">
                <div className="log-agent-info">
                  <div className="log-avatar" style={{ background: 'rgba(246,173,85,0.15)', color: 'var(--agent-4)' }}>C</div>
                  <span className="log-agent-name" style={{ color: 'var(--agent-4)' }}>CHIMERA-β</span>
                </div>
                <span className="log-time">04/05 · 23:45</span>
              </div>
              <div className="log-card-body">
                <div className="log-section">
                  <div className="log-section-label">📊 시장 분석</div>
                  <div className="log-text">백테스팅 결과 현재 스캘핑 전략의 <span className="log-highlight">수익비(R:R 1:1.2)</span>가 불충분합니다. 5분봉 노이즈로 인한 오신호율이 <span className="log-highlight">31%</span>로 과도합니다.</div>
                </div>
                <div className="log-section">
                  <div className="log-section-label">🔄 전략 변경 이유</div>
                  <div className="log-text">샤프지수 <span className="log-highlight">-0.31</span> 기록. 타임프레임을 5m → 15m으로 상향하고 ATR 필터를 강화하여 오신호를 줄이는 방향으로 전략을 재설계합니다.</div>
                </div>
                <div className="log-section">
                  <div className="log-section-label">⚙️ 파라미터 변경</div>
                  <div className="param-grid">
                    <div className="param-item">
                      <div className="param-name">timeframe</div>
                      <div className="param-vals">
                        <span className="param-old">5m</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new neutral">15m</span>
                      </div>
                    </div>
                    <div className="param-item">
                      <div className="param-name">atr_filter</div>
                      <div className="param-vals">
                        <span className="param-old">1.0×</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new up">1.8×</span>
                      </div>
                    </div>
                    <div className="param-item">
                      <div className="param-name">min_rr</div>
                      <div className="param-vals">
                        <span className="param-old">1.2</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new up">2.0</span>
                      </div>
                    </div>
                    <div className="param-item">
                      <div className="param-name">max_trades</div>
                      <div className="param-vals">
                        <span className="param-old">10</span>
                        <span className="param-arrow">→</span>
                        <span className="param-new down">5</span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>

          </div>

          {/* Backtest Quick Summary Table */}
          <div className="perf-section">
            <div className="perf-title">백테스트 성과 요약</div>
            <table className="perf-table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Total Return</th>
                  <th>Sharpe</th>
                  <th>Win%</th>
                  <th>MDD</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ color: 'var(--agent-1)', fontWeight: 600 }}>MINARA V2</td>
                  <td className="pos">+79.72%</td>
                  <td className="pos">2.41</td>
                  <td>67.4%</td>
                  <td className="neg">-12.3%</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--agent-2)', fontWeight: 600 }}>ARBITER V1</td>
                  <td className="pos">+22.78%</td>
                  <td className="pos">1.87</td>
                  <td>71.2%</td>
                  <td className="neg">-8.1%</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--agent-3)', fontWeight: 600 }}>NIM-ALPHA</td>
                  <td className="pos">+15.63%</td>
                  <td className="pos">1.23</td>
                  <td>52.1%</td>
                  <td className="neg">-18.9%</td>
                </tr>
                <tr>
                  <td style={{ color: 'var(--agent-4)', fontWeight: 600 }}>CHIMERA-β</td>
                  <td className="neg">-4.06%</td>
                  <td className="neg">-0.31</td>
                  <td>44.8%</td>
                  <td className="neg">-24.7%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
