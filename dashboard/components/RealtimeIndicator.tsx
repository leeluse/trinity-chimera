/**
 * RealtimeIndicator Component
 * 실시간 연결 상태 표시기
 */

import React from 'react';
import type { ConnectionStatus } from '../types';

interface RealtimeIndicatorProps {
  status: ConnectionStatus;
  lastUpdate?: string;
  latency?: number;
}

export const RealtimeIndicator: React.FC<RealtimeIndicatorProps> = ({
  status,
  lastUpdate,
  latency,
}) => {
  const statusConfig: Record<ConnectionStatus, {
    icon: string;
    label: string;
    color: string;
    bgColor: string;
    animate: boolean;
  }> = {
    connected: {
      icon: '🟢',
      label: 'Connected',
      color: 'text-emerald-600 dark:text-emerald-400',
      bgColor: 'bg-emerald-50 dark:bg-emerald-900/30',
      animate: false,
    },
    reconnecting: {
      icon: '🟡',
      label: 'Reconnecting...',
      color: 'text-yellow-600 dark:text-yellow-400',
      bgColor: 'bg-yellow-50 dark:bg-yellow-900/30',
      animate: true,
    },
    disconnected: {
      icon: '🔴',
      label: 'Disconnected',
      color: 'text-red-600 dark:text-red-400',
      bgColor: 'bg-red-50 dark:bg-red-900/30',
      animate: false,
    },
  };

  const config = statusConfig[status];

  const formatLastUpdate = (isoString?: string) => {
    if (!isoString) return 'Never';
    const date = new Date(isoString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);

    if (seconds < 60) return `${seconds}s ago`;
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className={`inline-flex items-center gap-3 rounded-full border px-4 py-2 ${
      config.bgColor
    } ${status === 'disconnected' ? 'border-red-200 dark:border-red-800' : 'border-transparent'}`}>
      {/* 상태 아이콘 */}
      <div className="relative">
        <span className={`text-lg ${config.animate ? 'animate-pulse' : ''}`}>
          {config.icon}
        </span>
        {config.animate && (
          <span className="absolute inset-0 animate-ping rounded-full bg-yellow-400 opacity-75"></span>
        )}
      </div>

      {/* 상태 정보 */}
      <div className="flex flex-col">
        <span className={`text-sm font-medium ${config.color}`}>
          {config.label}
        </span>

        {/* 마지막 업데이트 */}
        {lastUpdate && status !== 'disconnected' && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Updated {formatLastUpdate(lastUpdate)}
          </span>
        )}
      </div>

      {/* 지연시간 */}
      {latency !== undefined && status === 'connected' && (
        <div className="ml-2 flex items-center gap-1 border-l border-gray-300 pl-3 dark:border-gray-600">
          <svg className="h-3 w-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className={`text-xs font-medium ${
            latency < 100 ? 'text-emerald-500' :
            latency < 300 ? 'text-yellow-500' :
            'text-red-500'
          }`}>
            {latency}ms
          </span>
        </div>
      )}
    </div>
  );
};

/** 축소 버전 (아이콘만) */
export const RealtimeIndicatorCompact: React.FC<Pick<RealtimeIndicatorProps, 'status'>> = ({
  status,
}) => {
  const statusColors: Record<ConnectionStatus, string> = {
    connected: 'bg-emerald-500',
    reconnecting: 'bg-yellow-500 animate-pulse',
    disconnected: 'bg-red-500',
  };

  return (
    <div className="relative inline-flex h-3 w-3">
      <span className={`absolute inline-flex h-3 w-3 rounded-full ${statusColors[status]}`}></span>
      {status === 'reconnecting' && (
        <span className="absolute inline-flex h-3 w-3 animate-ping rounded-full opacity-75"></span>
      )}
    </div>
  );
};

/** 헤더용 인디케이터 */
export const RealtimeIndicatorHeader: React.FC<RealtimeIndicatorProps> = (props) => (
  <div className="flex items-center">
    <RealtimeIndicator {...props} />
  </div>
);

export default RealtimeIndicator;
