"use client";

import { useState, useRef, useEffect, useMemo, memo, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from 'rehype-raw';
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { Send, Plus, CheckCircle2, FileCode2, Loader2, Zap, Trash2, RotateCcw } from "lucide-react";
import { fetchWithBypass } from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  type?: "text" | "strategy" | "backtest" | "thought" | "invocation";
  data?: any;
}

interface ChatInterfaceProps {
  context?: Record<string, any>;
  onBacktestGenerated?: (payload: any) => void;
  onApplyCode?: (code: string, name?: string, payload?: any) => void;
}

const EXAMPLE_PROMPTS = [
  "돈치안/N봉 돌파 전략을 구축하고 ATR 포지션 관리와 가짜 돌파 필터를 결합해 주세요",
];

const formatChatRunError = (error: unknown): string => {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "요청 시간이 초과되었습니다. 백테스트가 길어질 수 있어 잠시 후 다시 시도해 주세요.";
  }

  if (error instanceof Error) {
    const msg = (error.message || "").trim();
    return msg || "알 수 없는 오류";
  }

  return "알 수 없는 오류";
};

// [PERF] Memoized individual message item to prevent re-rendering of entire list during streaming
const MessageItem = memo(({ msg, onShowCode }: { msg: ChatMessage, onShowCode: (code: string, title?: string, payload?: any) => void }) => {
  return (
    <div className={`flex flex-col py-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
      {msg.role === 'user' ? (
        <div className="bg-purple-600/20 border border-purple-500/20 rounded-2xl px-4 py-2 max-w-[85%] text-sm text-purple-100 shadow-sm">
          {msg.content}
        </div>
      ) : (
        <div className="w-full space-y-4">
            {msg.type === 'invocation' && (
              <div className="flex flex-col gap-1.5 mb-2 animate-in slide-in-from-left duration-300">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-xl">
                  <Zap size={14} className="text-blue-400 fill-blue-400/20" />
                  <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">분류됨: {msg.content}</span>
                </div>
                {(msg.data?.router_model || msg.data?.model) && (
                  <div className="flex items-center gap-1.5 ml-3">
                    <div className="w-1 h-1 rounded-full bg-blue-500/40" />
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-tighter">
                      분류 모델: {msg.data?.router_model || msg.data?.model}
                    </span>
                  </div>
                )}
                {msg.data?.models && (
                  <div className="flex items-center gap-1.5 ml-3">
                    <div className="w-1 h-1 rounded-full bg-blue-500/40" />
                    <span className="text-[9px] font-bold text-slate-500 tracking-tighter">
                      파이프라인: 분석 {msg.data.models.analysis} · 코드 {msg.data.models.code} · 요약 {msg.data.models.quick}
                    </span>
                  </div>
                )}
              </div>
            )}

            {msg.role === 'assistant' && msg.type === 'text' && (
            <div className="text-[11px] text-slate-400/90 leading-normal px-1 font-medium markdown-content pt-1 transition-all">
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                >
                  {msg.content
                    ?.replace(/<(thought|think|think_process|reasoning)>[\s\S]*?<\/\1>/gi, '')
                    ?.replace(/<\/?(thought|think|think_process|reasoning)[^>]*>/gi, '')
                  }
                </ReactMarkdown>
            </div>
          )}

          {msg.type === 'thought' && (
            <details className="group mb-2 max-w-[95%]">
              <summary className="flex items-center gap-2 px-3 py-2 bg-amber-500/5 border border-amber-500/10 rounded-xl cursor-pointer hover:bg-amber-500/10 transition-all list-none">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-500/40 animate-pulse" />
                <span className="text-[10px] font-bold tracking-widest uppercase text-amber-400/60">AI Reasoning</span>
                <Plus size={10} className="ml-auto text-amber-400/40 group-open:rotate-45 transition-transform" />
              </summary>
              <div className="mt-2 px-4 py-3 bg-amber-500/[0.02] border border-amber-500/5 rounded-xl text-[11px] text-slate-400/90 leading-relaxed font-medium italic thought-markdown markdown-content overflow-hidden">
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                >
                  {msg.content?.replace(/<\/?(thought|think)[^>]*>/gi, '')}
                </ReactMarkdown>
              </div>
            </details>
          )}

          {msg.type === 'strategy' && (
            <div className="flex flex-col bg-white/[0.03] border border-white/[0.08] rounded-xl p-4 shadow-xl gap-3 backdrop-blur-md mb-6">
              <div className="flex items-center gap-2 text-[#4ade80]">
                <CheckCircle2 size={18} />
                <span className="text-xs font-bold tracking-tight uppercase">전략 생성 완료</span>
              </div>
              <div className="h-px bg-white/[0.05] my-2" />
              <div className="space-y-1.5">
                <h3 className="text-[13px] font-bold text-white/90">{msg.data.title}</h3>
                <p className="text-[11px] text-slate-400 leading-relaxed italic font-medium">
                  {msg.data.description}
                </p>
                
                {msg.data.code && (
                  <div className="mt-2 rounded-lg bg-black/40 border border-white/5 p-2 overflow-hidden">
                    <div className="max-h-[80px] overflow-y-auto overflow-x-hidden custom-scrollbar">
                      <pre className="text-[11px] text-purple-200/60 font-mono leading-tight break-all whitespace-pre-wrap">
                        {msg.data.code}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
              <button
                onClick={() => onShowCode(String(msg.data?.code || ""), msg.data?.title, msg.data?.backtest_payload)}
                className="flex items-center justify-center gap-2 w-full px-4 py-2 bg-purple-600/10 border border-purple-500/30 rounded-xl text-[10px] font-bold text-purple-100 hover:bg-purple-600/20 transition-all active:scale-95"
              >
                <FileCode2 size={12} />
                전략 코드 에디터에 적용
              </button>
            </div>
          )}

          {msg.type === 'backtest' && (
            <div className="flex flex-col bg-white/[0.03] border border-white/[0.08] rounded-xl gap-3 p-4 shadow-xl backdrop-blur-md">
              <div className="flex items-center gap-2 text-[#4ade80]">
                <CheckCircle2 size={18} />
                <span className="text-xs font-bold tracking-tight uppercase">백테스트 완료</span>
              </div>
              <div className="h-px bg-white/[0.05]" />
              <div className="grid grid-cols-3 gap-y-4 gap-x-2">
                <StatItem label="수익" value={msg.data.ret} color="text-[#4ade80]" />
                <StatItem label="손실폭" value={msg.data.mdd} color="text-[#fb7185]" />
                <StatItem label="승률" value={msg.data.winRate} />
                <StatItem label="샤프 지수" value={msg.data.sharpe} />
                <StatItem label="거래" value={msg.data.trades} />
                <StatItem label="손익 비율" value={msg.data.pf} />
              </div>
              
              <button
                onClick={() => onShowCode(String(msg.data?.code || ""), "Mined Strategy", msg.data?.payload)}
                className="mt-2 flex items-center justify-center gap-2 w-full px-4 py-1.5 bg-white/[0.05] border border-white/[0.1] rounded-lg text-[10px] font-bold text-slate-400 hover:bg-white/[0.1] hover:text-white transition-all"
              >
                <FileCode2 size={12} />
                에디터에 다시 적용
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

export default function ChatInterface({ context = {}, onBacktestGenerated, onApplyCode }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState("AI 분석 중...");
  const [currentStage, setCurrentStage] = useState(0);
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  // stage 이벤트마다 새 블록을 강제 시작하기 위한 key
  const currentStageIdRef = useRef<string>("");

  // 🆔 세션 ID 관리 (localStorage 유지)
  const sessionIdRef = useRef<string>("");
  const [isGlobalMode, setIsGlobalMode] = useState(true);
  const [sessionInput, setSessionInput] = useState("");
  const [isClearing, setIsClearing] = useState(false);

  const loadHistory = async (sid?: string, global: boolean = true) => {
    try {
      const queryParams = new URLSearchParams({ 
        t: Date.now().toString(),
        limit: "200" // 글로벌 모드이므로 좀 더 많이 가져옴
      });
      if (!global && sid) {
        queryParams.set("session_id", sid);
      }
      
      const res = await fetchWithBypass(
        `/api/chat/history?${queryParams.toString()}`,
        { 
          timeoutMs: 15000,
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
          }
        }
      );
      if (!res.ok) return;
      const data = await res.json();
      if (data.success && Array.isArray(data.messages)) {
        const historyMessages: ChatMessage[] = data.messages
          .map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content || "",
            type: (m.type === "analysis" ? "text" : (m.type || "text")) as any,
            data: m.data ?? {},
          }));
        setMessages(historyMessages);
      }
    } catch (err) {
      console.error("History load failed:", err);
    }
  };

  useEffect(() => {
    let sid = localStorage.getItem("chat_session_id");
    if (!sid) {
      sid = `session-${Math.random().toString(36).substr(2, 9)}-${Date.now()}`;
      localStorage.setItem("chat_session_id", sid);
    }
    sessionIdRef.current = sid;
    setSessionInput(sid);
    
    // 기본적으로 전체 히스토리(글로벌) 로드
    loadHistory(undefined, true);
  }, []);

  const handleSwitchSession = (newSid: string) => {
    if (!newSid.trim()) return;
    localStorage.setItem("chat_session_id", newSid.trim());
    sessionIdRef.current = newSid.trim();
    setSessionInput(newSid.trim());
    setIsGlobalMode(false);
    loadHistory(newSid.trim(), false);
  };

  const toggleGlobalMode = () => {
    const nextGlobal = !isGlobalMode;
    setIsGlobalMode(nextGlobal);
    loadHistory(sessionIdRef.current, nextGlobal);
  };

  const handleNewSession = () => {
    const newSid = `session-${Math.random().toString(36).substr(2, 9)}-${Date.now()}`;
    localStorage.setItem("chat_session_id", newSid);
    sessionIdRef.current = newSid;
    setSessionInput(newSid);
    setIsGlobalMode(false);
    setMessages([]);
    // 새 세션 시작 후 히스토리 다시 불러오기 (세션 목록 갱신용)
    loadSessions();
  };

  const [sessions, setSessions] = useState<any[]>([]);
  const loadSessions = async () => {
    try {
      const res = await fetchWithBypass("/api/chat/sessions?limit=20");
      if (res.ok) {
        const data = await res.json();
        if (data.success) setSessions(data.sessions || []);
      }
    } catch (e) {
      console.error("Sessions fetch failed:", e);
    }
  };

  // [PERF] Throttled session loading during streaming
  const lastLoadSessionsRef = useRef(0);
  const throttleLoadSessions = () => {
    const now = Date.now();
    if (now - lastLoadSessionsRef.current > 2000) {
      loadSessions();
      lastLoadSessionsRef.current = now;
    }
  };

  useEffect(() => {
    if (isLoading) {
      throttleLoadSessions();
    } else {
      loadSessions();
    }
  }, [isLoading, (messages.length > 0 ? messages[messages.length-1].content.length : 0)]);

  const handleClearSession = async () => {
    const sid = sessionIdRef.current;
    if (!sid || isClearing) return;
    if (!confirm(`현재 세션(${sid.slice(0, 20)}...)의 대화를 모두 삭제할까요?`)) return;
    setIsClearing(true);
    try {
      await fetchWithBypass(`/api/chat/history?session_id=${encodeURIComponent(sid)}`, {
        method: "DELETE",
      });
      if (isGlobalMode) {
        loadHistory(undefined, true);
      } else {
        setMessages([]);
      }
      loadSessions();
    } catch (e) {
      console.error("Clear failed:", e);
    } finally {
      setIsClearing(false);
    }
  };

  /** [DEPRECATED] Manual scroll handling replaced by Virtuoso followOutput */
  /*
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);
  */

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const appendMessage = (message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  };

  const handleShowCode = useCallback((code: string, title?: string, payload?: any) => {
    if (!code) return;
    if (onApplyCode) {
      onApplyCode(code, title, payload);
    }
  }, [onApplyCode]);

  const handleSend = async (presetMessage?: string) => {
    const raw = presetMessage ?? input;
    if (!raw.trim() || isLoading) return;

    // Abort previous request if still running
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const userMessage = raw.trim();
    const newUserMsg: ChatMessage = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: "user",
      content: userMessage
    };

    appendMessage(newUserMsg);
    setInput("");
    setIsLoading(true);
    setCurrentStage(0);
    currentStageIdRef.current = "";
    setStatusText("AI 분석 중...");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // LLM에 보낼 히스토리: 너무 길면 Context Window 초과 위험이 있으므로 최근 15개로 제한
      const history = messages
        .filter((msg) => msg.content && msg.content.trim())
        .map((msg) => ({
          role: msg.role,
          content: msg.content,
        }))
        .slice(-15); 

      // Vercel/Local 모두 Next.js API 프록시 경로를 고정 사용
      const url = `/api/chat/run?t=${Date.now()}`;

      const response = await fetchWithBypass(url, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
          "Cache-Control": "no-cache",
          "Pragma": "no-cache"
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionIdRef.current,
          context,
          history,
        }),
        signal: controller.signal,
        cache: "no-store", // [중요] 브라우저 캐시 무시
        timeoutMs: 300000
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Stream reader not available");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          
          try {
            const raw = line.replace("data: ", "").trim();
            if (!raw) continue;
            const event = JSON.parse(raw);
            
            switch (event.type) {
              case "status":
                setStatusText(event.content);
                break;

              // stage 이벤트: 새 덩어리(블록) 시작을 강제함
              case "stage": {
                const newStageId = `stage-${event.stage}-${Date.now()}`;
                currentStageIdRef.current = newStageId;
                setCurrentStage(event.stage);
                setStatusText(event.label ?? `단계 ${event.stage} 진행 중...`);
                break;
              }

              case "thought":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const stageId = currentStageIdRef.current;
                  // 어시스턴트의 연속된 추론은 무조건 하나의 블록으로 병합
                  const canAppend = last && last.role === "assistant" && last.type === "thought";
                  
                  if (canAppend) {
                    const next = [...prev];
                    next[next.length - 1] = { ...last, content: last.content + event.content };
                    return next;
                  }
                  return [...prev, {
                    id: `thought-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                    role: "assistant",
                    content: event.content,
                    type: "thought",
                  }];
                });
                break;

              case "strategy":
                appendMessage({
                  id: `${Date.now()}-strategy`,
                  role: "assistant",
                  content: "",
                  type: "strategy",
                  data: event.data,
                });
                break;

              case "backtest":
                appendMessage({
                  id: `${Date.now()}-backtest`,
                  role: "assistant",
                  content: "",
                  type: "backtest",
                  data: {
                    ...event.data,
                    // 서버에서 이제 data 안에 code를 포함해서 보냄
                    code: event.data.code || event.strategy_code,
                    payload: event.payload
                  },
                });
                
                // [AUTO-APPLY] 백테스트 완료 시 발굴된 코드를 에디터에 즉시 자동 적용 (사용자 편의성)
                const finalCode = event.data.code || event.strategy_code;
                if (finalCode && onApplyCode) {
                  onApplyCode(finalCode, event.data?.title || "Mined Strategy", event.payload);
                }
                
                if (event.payload && onBacktestGenerated) {
                  onBacktestGenerated(event.payload);
                }
                break;

              case "invocation":
                appendMessage({
                  id: `${Date.now()}-invoke-${event.skill}`,
                  role: "assistant",
                  content: event.label || event.skill,
                  type: "invocation",
                  data: { model: event.model, router_model: event.router_model, models: event.models }
                });
                setStatusText(`⚡ ${event.label || event.skill} 발동 중... ${event.model ? `(${event.model})` : ''}`);
                break;

              case "analysis":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const stageId = currentStageIdRef.current;
                  // 같은 컨텍스트면 이어 붙임
                  const lastId = last?.id || "";
                  const isSameContext = stageId ? lastId.startsWith(stageId) : (lastId && !lastId.includes("stage-"));
                  const canAppend = last && last.role === "assistant" && last.type === "text" && isSameContext;

                  if (canAppend) {
                    const next = [...prev];
                    next[next.length - 1] = { ...last, content: last.content + event.content };
                    return next;
                  }
                  // 새 stage이거나 직전이 다른 타입이면 새 블록 생성
                  return [...prev, {
                    id: `${stageId}-${Date.now()}-analysis-${Math.random().toString(36).substr(2, 5)}`,
                    role: "assistant",
                    content: event.content,
                    type: "text",
                  }];
                });
                break;

              case "error":
                throw new Error(event.content);
            }
          } catch (err) {
            console.error("Event Parse Error:", err, line);
          }
        }
      }
    } catch (e) {
      console.error(e);
      const errorMessage = formatChatRunError(e);
      const extraHint = /failed to fetch|networkerror|http 502|http 503|http 504/i.test(errorMessage)
        ? "\n연결 힌트: 프론트가 백엔드에 접근하지 못했습니다. 터널 URL 또는 NEXT_PUBLIC_API_URL 설정을 확인해 주세요."
        : "";
      appendMessage({
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `전략 생성/백테스트 실행 중 오류가 발생했습니다.\n사유: ${errorMessage}${extraHint}`,
        type: "text",
      });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };


  return (
    <div className="flex flex-col h-full bg-[#060912]/20">
      {/* 🆔 헤더 세션 컨트롤 바 */}
      <div className="px-4 py-3 border-b border-white/[0.05] bg-[#0a0f1d]/40 backdrop-blur-md flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            onClick={toggleGlobalMode}
            className={`px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest transition-all border ${
              isGlobalMode 
                ? 'bg-purple-500/20 border-purple-500/50 text-purple-300 shadow-[0_0_15px_rgba(168,85,247,0.15)]' 
                : 'bg-white/[0.03] border-white/[0.1] text-slate-500 hover:text-slate-300'
            }`}
          >
            {isGlobalMode ? 'Global On' : 'Session Only'}
          </button>
          
          <select 
            value={isGlobalMode ? "" : sessionIdRef.current}
            onChange={(e) => e.target.value && handleSwitchSession(e.target.value)}
            className="bg-white/[0.03] border border-white/[0.08] rounded-lg px-2 py-1 text-[10px] text-slate-400 focus:ring-0 focus:border-purple-500/50 outline-none max-w-[150px] font-mono"
          >
            <option value="" disabled>{isGlobalMode ? "All Conversations" : "Select Session"}</option>
            {sessions.map(s => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id.slice(0, 15)}... ({s.count})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={handleNewSession}
            className="p-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-slate-400 hover:text-purple-300 hover:border-purple-500/30 transition-all active:scale-95"
            title="New Chat"
          >
            <Plus size={14} />
          </button>
          <button
            onClick={() => loadHistory(sessionIdRef.current, isGlobalMode)}
            className="p-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-slate-400 hover:text-slate-200 transition-all active:scale-95"
            title="Refresh"
          >
            <RotateCcw size={14} />
          </button>
          {!isGlobalMode && (
            <button
              onClick={handleClearSession}
              disabled={isClearing}
              className="p-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-slate-500 hover:text-red-400 hover:border-red-500/30 transition-all active:scale-95 disabled:opacity-40"
              title="Delete Session"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Chat Messages - Virtualized for Scale */}
      <div className="flex-1 min-h-0 overflow-hidden relative">
        <Virtuoso
          ref={virtuosoRef}
          data={messages}
          followOutput={(isAtBottom) => isAtBottom ? 'smooth' : false}
          className="custom-scrollbar"
          alignToBottom
          itemContent={(index, msg) => (
            <div className="px-4">
              <MessageItem 
                msg={msg} 
                onShowCode={handleShowCode} 
              />
            </div>
          )}
          components={{
            Header: () => (
              <div className="pt-4">
                {messages.length === 0 && !isLoading && !isGlobalMode && (
                  <div className="flex flex-col gap-3 items-center justify-center space-y-4 opacity-80 py-10">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center border border-purple-500/20 mb-2">
                      <Zap size={24} className="text-purple-400 animate-pulse" />
                    </div>
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Get Started with AI Strategy</h3>
                    <div className="flex flex-col gap-2 w-full max-w-sm px-4">
                      {EXAMPLE_PROMPTS.map((prompt, i) => (
                        <button
                          key={i}
                          onClick={() => handleSend(prompt)}
                          className="text-left px-5 py-3 rounded-xl bg-white/[0.02] border border-white/[0.05] hover:border-purple-500/30 hover:bg-purple-500/5 transition-all group"
                        >
                          <p className="text-[11px] text-slate-400 group-hover:text-purple-300 leading-relaxed font-medium">
                            {prompt}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          }}
        />
      </div>

      {/* Modern Integrated Chat Input Area */}
      <div className="px-5 pb-6 pt-2 bg-transparent">
        <div className="max-w-4xl mx-auto flex flex-col gap-3">
          
          {/* Subtle Status Info */}
          {isLoading && (
            <div className="flex items-center gap-3 px-4 animate-in fade-in slide-in-from-bottom-1 duration-500">
              <div className="relative flex items-center">
                <Loader2 size={12} className="animate-spin text-purple-500" />
                <div className="absolute inset-0 bg-purple-500/20 blur-md rounded-full animate-pulse" />
              </div>
              <span className="text-[10px] font-black tracking-[0.2em] text-slate-400 uppercase">
                {statusText}
              </span>
              <div className="flex gap-1.5 ml-auto items-center">
                {[1, 2, 3, 4, 5].map(s => (
                  <div 
                    key={s} 
                    className={`h-1.5 w-1.5 rounded-full transition-all duration-700 ease-out ${
                      s <= currentStage 
                        ? 'bg-purple-500 shadow-[0_0_10px_rgba(168,85,247,0.8)] scale-110' 
                        : 'bg-white/10'
                    }`} 
                  />
                ))}
              </div>
            </div>
          )}

          {/* Integrated Input Bar */}
          <div className={`relative flex items-center transition-all duration-500 rounded-[22px] p-1.5 backdrop-blur-2xl border ${
            isLoading 
              ? 'border-purple-500/20 bg-purple-500/5 shadow-[0_0_30px_rgba(168,85,247,0.05)]' 
              : 'border-white/[0.08] bg-white/[0.02] shadow-2xl hover:border-white/[0.12] focus-within:border-purple-500/30 focus-within:bg-white/[0.04]'
          }`}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={isLoading}
              placeholder={isLoading ? "" : "Explore AI Trading Ideas..."}
              className="flex-1 bg-transparent border-none focus:ring-0 text-[13px] text-slate-100 placeholder:text-slate-600 resize-none py-2.5 px-4 max-h-40 overflow-y-auto custom-scrollbar"
              rows={1}
            />
            
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className={`p-2.5 rounded-[18px] transition-all duration-300 flex items-center justify-center ${
                input.trim() && !isLoading 
                  ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/20 hover:scale-105 hover:bg-purple-500 active:scale-95' 
                  : 'text-slate-700 opacity-40 cursor-not-allowed'
              }`}
            >
              <Send size={18} fill={input.trim() && !isLoading ? "currentColor" : "none"} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatItem({ label, value, color = "text-white" }: { label: string, value: string, color?: string }) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-tight leading-none">{label}</div>
      <div className={`text-sm font-black tracking-tight ${color}`}>{value}</div>
    </div>
  );
}
