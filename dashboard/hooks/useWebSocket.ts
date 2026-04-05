/**
 * useWebSocket Hook
 * WebSocket 연결 및 실시간 데이터 수신 관리
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { ConnectionStatus, WebSocketEvent } from '../types';

interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
  status: ConnectionStatus;
  lastEvent: WebSocketEvent | null;
  latency: number;
  lastUpdate: string | null;
  sendMessage: (message: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    url = 'ws://localhost:8000/ws',
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [latency, setLatency] = useState<number>(0);

  const ws = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const latencyCheck = useRef<NodeJS.Timeout | null>(null);
  const lastPingTime = useRef<number>(0);

  // 연결 해제
  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
    if (latencyCheck.current) {
      clearInterval(latencyCheck.current);
      latencyCheck.current = null;
    }

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    setStatus('disconnected');
    reconnectAttempts.current = 0;
  }, []);

  // 연결
  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    disconnect();
    setStatus('reconnecting');

    try {
      const websocket = new WebSocket(url);

      websocket.onopen = () => {
        setStatus('connected');
        reconnectAttempts.current = 0;
        lastPingTime.current = Date.now();

        // 지연 시간 체크 시작
        latencyCheck.current = setInterval(() => {
          if (websocket.readyState === WebSocket.OPEN) {
            lastPingTime.current = Date.now();
            websocket.send(JSON.stringify({ type: 'ping' }));
          }
        }, 5000);
      };

      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Ping 응답 처리
          if (data.type === 'pong') {
            const now = Date.now();
            setLatency(now - lastPingTime.current);
            return;
          }

          setLastEvent(data as WebSocketEvent);
          setLastUpdate(new Date().toISOString());
        } catch (error) {
          console.error('WebSocket message parse error:', error);
        }
      };

      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        setStatus('disconnected');
      };

      websocket.onclose = () => {
        setStatus('disconnected');

        // 재연결 시도
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          reconnectTimeout.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      ws.current = websocket;
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setStatus('disconnected');

      // 재연결 시도
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current++;
        reconnectTimeout.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    }
  }, [url, disconnect, reconnectInterval, maxReconnectAttempts]);

  // 메시지 전송
  const sendMessage = useCallback((message: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  // 자동 연결
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    status,
    lastEvent,
    latency,
    lastUpdate,
    sendMessage,
    connect,
    disconnect,
  };
};

export default useWebSocket;
