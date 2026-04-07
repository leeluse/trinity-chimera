"use client";

import React, { useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const BacktestPage = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    const createGradient = (ctx: CanvasRenderingContext2D) => {
      const gradient = ctx.createLinearGradient(0, 0, 0, 400);
      gradient.addColorStop(0, 'rgba(0, 255, 204, 0.3)');
      gradient.addColorStop(1, 'rgba(0, 255, 204, 0)');
      return gradient;
    };

    const chartData = {
      labels: Array.from({ length: 30 }, (_, i) => `Day ${i + 1}`),
      datasets: [
        {
          label: 'Equity Curve',
          data: [10000, 10200, 10100, 10500, 10800, 10700, 11200, 11500, 11300, 12000, 12500, 12300, 12800, 13200, 13000, 13500, 14000, 13800, 14500, 15000, 14800, 15500, 16000, 15800, 16500, 17000, 16800, 17500, 18000, 18500],
          borderColor: '#00ffcc',
          backgroundColor: (context: any) => {
            const chart = context.chart;
            const { ctx } = chart;
            return createGradient(ctx);
          },
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
      ],
    };

    setData(chartData);
  }, []);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleColor: '#94a3b8',
        bodyColor: '#00ffcc',
        borderColor: '#334155',
        borderWidth: 1,
        cornerRadius: 4,
        displayColors: false,
        callbacks: {
          label: (context: any) => `Balance: $${context.parsed.y.toLocaleString()}`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
        ticks: { color: '#64748b', fontSize: 11 },
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
        ticks: {
          color: '#64748b',
          fontSize: 11,
          callback: (value: any) => `$${value.toLocaleString()}`
        },
      },
    },
  };

  return (
    <<divdiv className="min-h-screen bg-[#0a0e14] text-slate-300 p-6 font-mono">
      {/* Header */}
      <<divdiv className="flex justify-between items-center mb-8 border-b border-slate-800 pb-4">
        <div>
          <<hh1 className="text-2xl font-bold text-white tracking-tight">
            STRATEGY <<spanspan className="text-[#00ffcc]">BACKTEST</span>
          </h1>
          <<pp className="text-xs text-slate-500 mt-1">QUANT TERMINAL v1.0 // SYSTEM STATUS: OPTIMAL</p>
        </div>
        <<divdiv className="flex gap-3">
          <<buttonbutton className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs rounded border border-slate-700 transition-all">
            IMPORT CONFIG
          </button>
          <<buttonbutton className="px-4 py-2 bg-[#00ffcc] hover:bg-[#00e6b3] text-black font-bold text-xs rounded transition-all shadow-[0_0_15px_rgba(0,255,204,0.3)]">
            RUN TEST
          </button>
        </div>
      </div>

      <<divdiv className="grid grid-cols-12 gap-6">
        {/* Left Panel: Parameters */}
        <<divdiv className="col-span-12 lg:col-span-3 space-y-6">
          <<divdiv className="bg-[#111720] border border-slate-800 rounded-lg p-5">
            <<hh2 className="text-sm font-bold text-slate-400 mb-4 flex items-center gap-2">
              <<spanspan className="w-2 h-2 bg-[#00ffcc] rounded-full"></span>
              CONFIGURATION
            </h2>
            <<divdiv className="space-y-4">
              {[
                { label: 'Timeframe', value: '1H', key: 'tf' },
                { label: 'Lookback Period', value: '200', key: 'lb' },
                { label: 'Risk per Trade', value: '2.0%', key: 'rp' },
                { label: 'Slippage', value: '0.1%', key: 'sl' },
                { label: 'Trading Pair', value: 'BTC/USDT', key: 'tp' },
              ].map((item) => (
                <<divdiv key={item.key} className="group">
                  <<labellabel className="text-[10px] text-slate-500 block mb-1 uppercase tracking-widest">{item.label}</label>
                  <<inputinput
                    type="text"
                    defaultValue={item.value}
                    className="w-full bg-[#0a0e14] border border-slate-700 text-white text-xs p-2 rounded focus:border-[#00ffcc] outline-none transition-colors group-hover:border-slate-600"
                  />
                </div>
              ))}
            </div>
          </div>

          <<divdiv className="bg-[#111720] border border-slate-800 rounded-lg p-5">
            <<hh2 className="text-sm font-bold text-slate-400 mb-4 flex items-center gap-2">
              <<spanspan className="w-2 h-2 bg-[#ff3366] rounded-full"></span>
              FILTERS
            </h2>
            <<divdiv className="space-y-3">
              {['HMM Regime Filter', 'Volatility Guard', 'Trend Alignment', 'Liquidity Check'].map((filter) => (
                <<divdiv key={filter} className="flex items-center justify-between p-2 bg-[#0a0e14] border border-slate-800 rounded text-[11px]">
                  <span>{filter}</span>
                  <<inputinput type="checkbox" className="accent-[#00ffcc] w-3 h-3" defaultChecked />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Middle/Right Panel: Main Content */}
        <<divdiv className="col-span-12 lg:col-span-9 space-y-6">
          {/* Top Metrics */}
          <<divdiv className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Total Return', value: '+85.0%', color: 'text-[#00ffcc]' },
              { label: 'Sharpe Ratio', value: '2.41', color: 'text-white' },
              { label: 'Max Drawdown', value: '-12.4%', color: 'text-[#ff3366]' },
              { label: 'Win Rate', value: '68.2%', color: 'text-white' },
            ].map((metric) => (
              <<divdiv key={metric.label} className="bg-[#111720] border border-slate-800 p-4 rounded-lg">
                <<pp className="text-[10px] text-slate-500 uppercase tracking-tighter mb-1">{metric.label}</p>
                <<pp className={`text-xl font-bold ${metric.color}`}>{metric.value}</p>
              </div>
            ))}
          </div>

          {/* Main Chart */}
          <<divdiv className="bg-[#111720] border border-slate-800 rounded-lg p-6 h-[450px] relative">
            <<divdiv className="absolute top-6 left-6 z-10">
              <<hh2 className="text-sm font-bold text-slate-400 flex items-center gap-2">
                EQUITY CURVE
              </h2>
            </div>
            <<divdiv className="h-full w-full pt-8">
              {data && <<LineLine data={data} options={options} />}
            </div>
          </div>

          {/* Bottom Table: Trade Log */}
          <<divdiv className="bg-[#111720] border border-slate-800 rounded-lg overflow-hidden">
            <<divdiv className="p-4 border-b border-slate-800 flex justify-between items-center">
              <<hh2 className="text-sm font-bold text-slate-400">TRADE EXECUTION LOG</h2>
              <<spanspan className="text-[10px] text-slate-600">Showing last 50 trades</span>
            </div>
            <<divdiv className="overflow-x-auto">
              <<tabletable className="w-full text-left text-[11px]">
                <thead>
                  <<trtr className="bg-[#0a0e14] text-slate-500 uppercase">
                    <<thth className="p-3 font-medium">Time</th>
                    <<thth className="p-3 font-medium">Side</th>
                    <<thth className="p-3 font-medium">Entry Price</th>
                    <<thth className="p-3 font-medium">Exit Price</th>
                    <<thth className="p-3 font-medium">PnL (%)</th>
                    <<thth className="p-3 font-medium">Status</th>
                  </tr>
                </thead>
                <<tbodytbody className="divide-y divide-slate-800">
                  {[
                    { time: '2026-04-07 14:00', side: 'LONG', entry: '64,200', exit: '65,100', pnl: '+1.4%', status: 'WIN' },
                    { time: '2026-04-07 10:30', side: 'SHORT', entry: '64,800', exit: '64,950', pnl: '-0.2%', status: 'LOSS' },
                    { time: '2026-04-06 22:15', side: 'LONG', entry: '63,500', exit: '64,100', pnl: '+0.9%', status: 'WIN' },
                    { time: '2026-04-06 18:00', side: 'LONG', entry: '63,100', exit: '63,900', pnl: '+1.2%', status: 'WIN' },
                    { time: '2026-04-06 12:00', side: 'SHORT', entry: '64,000', exit: '63,800', pnl: '+0.3%', status: 'WIN' },
                  ].map((trade, i) => (
                    <<trtr key={i} className="hover:bg-slate-800/30 transition-colors">
                      <<tdtd className="p-3 text-slate-400">{trade.time}</td>
                      <<tdtd className={`p-3 font-bold ${trade.side === 'LONG' ? 'text-[#00ffcc]' : 'text-[#ff3366]'}`}>{trade.side}</td>
                      <<tdtd className="p-3">${trade.entry}</td>
                      <<tdtd className="p-3">${trade.exit}</td>
                      <<tdtd className={`p-3 font-bold ${trade.pnl.startsWith('+') ? 'text-[#00ffcc]' : 'text-[#ff3366]'}`}>{trade.pnl}</td>
                      <<tdtd className="p-3">
                        <<spanspan className={`px-2 py-0.5 rounded-full text-[9px] ${trade.status === 'WIN' ? 'bg-[#00ffcc]/10 text-[#00ffcc]' : 'bg-[#ff3366]/10 text-[#ff3366]'}`}>
                          {trade.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BacktestPage;
