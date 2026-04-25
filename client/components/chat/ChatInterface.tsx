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
  type?: "text" | "strategy" | "backtest" | "thought" | "invocation" | "design" | "choice";
  data?: any;
}

interface ChatInterfaceProps {
  context?: Record<string, any>;
  onBacktestGenerated?: (payload: any) => void;
  onApplyCode?: (code: string, name?: string, payload?: any) => void;
}
// const MAX_THINKING_CHARS = 10000; // 생략 비활성화됨 (사용 요청)

const EXAMPLE_PROMPTS = [
  "돈치안/N봉 돌파 전략을 구축하고 ATR 포지션 관리와 가짜 돌파 필터를 결합해 주세요",
];

const SKILL_STAGE_META: Record<string, { total: number; showProgress: boolean }> = {
  CREATE_STRATEGY: { total: 5, showProgress: true },
  MODIFY_STRATEGY: { total: 5, showProgress: true },
  RUN_EVOLUTION: { total: 5, showProgress: true },
  RUN_BACKTEST: { total: 5, showProgress: true },
  EXPLAIN_STRATEGY: { total: 1, showProgress: false },
  RISK_ANALYSIS: { total: 1, showProgress: false },
  CODE_REVIEW: { total: 1, showProgress: false },
  SUGGEST_NEXT: { total: 1, showProgress: false },
  CODE_FROM_DESIGN: { total: 2, showProgress: true },
};

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
const MessageItem = memo(({ msg, onShowCode, onSendMessage, isStreaming, onChoiceSelect, onDesignCodeRequest }: {
  msg: ChatMessage,
  onShowCode: (code: string, title?: string, payload?: any) => void,
  onSendMessage?: (text: string) => void,
  isStreaming?: boolean,
  onChoiceSelect?: (choiceValue: string, originalMessage?: string, design?: string) => void,
  onDesignCodeRequest?: (designContent: string) => void,
}) => {
  let mainContent = msg.content || "";
  let thinkingContent = "";
  let isThinkingStreaming = false;

  // thought 타입: 스트리밍 중 = 열림, 완료 후 = 자동 접힌
  if (msg.role === 'assistant' && msg.type === 'thought') {
    thinkingContent = (msg.content || "").replace(/<\/?(thought|think|think_process|reasoning)[^>]*>/gi, '').trim();
    mainContent = "";
    isThinkingStreaming = !!isStreaming; // 스트리밍 중이면 true
  } else if (msg.role === 'assistant' && msg.type === 'text') {
    // text 타입 내 <think> 태그 파싱
    const closedMatch = mainContent.match(/<(thought|think|think_process|reasoning)>([\/\s\S]*?)<\/\1>/i);
    const streamingMatch = mainContent.match(/<(thought|think|think_process|reasoning)>([\/\s\S]*)$/i);

    if (closedMatch) {
      thinkingContent = closedMatch[2].trim();
      mainContent = mainContent.replace(closedMatch[0], "").trim();
    } else if (streamingMatch) {
      thinkingContent = streamingMatch[2].replace(/<\/?(thought|think|think_process|reasoning)[^>]*>/gi, '').trim();
      mainContent = mainContent.replace(streamingMatch[0], "").trim();
      isThinkingStreaming = true;
    }
    mainContent = mainContent.replace(/<\/?(thought|think|think_process|reasoning)[^>]*>/gi, '').trim();
  }

  // 자동 스크롤: thought 컨텐츠 div ref
  const thoughtScrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (isThinkingStreaming && thoughtScrollRef.current) {
      thoughtScrollRef.current.scrollTop = thoughtScrollRef.current.scrollHeight;
    }
  });

  const displayThinkingContent = thinkingContent;

  return (
    <div className={`flex flex-col py-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
      {msg.role === 'user' ? (
        <div className="bg-purple-600/20 border border-purple-500/20 rounded-2xl px-4 py-2 max-w-[85%] text-sm text-purple-100 shadow-sm animate-in slide-in-from-right-2 duration-300">
          {msg.content}
        </div>
      ) : (
        <div className="w-full space-y-4 animate-in fade-in duration-500">
            {msg.type === 'invocation' && (
              <div className="flex flex-col gap-1.5 mb-2">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-xl">
                  <Zap size={14} className="text-blue-400 fill-blue-400/20" />
                  <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">분류됨: {msg.content}</span>
                </div>
                {msg.data?.skill && (
                  <div className="flex items-center gap-1.5 ml-3">
                    <div className="w-1 h-1 rounded-full bg-blue-500/40" />
                    <span className="text-[9px] font-bold text-blue-300/80 tracking-tight">
                      [SKILL: {msg.data.skill}]
                    </span>
                  </div>
                )}
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

            {thinkingContent && (
              // 스트리밍 중: 열림 + 스피너 / 완료 후: 자동 접힌
              <details className="group mb-2 max-w-[95%]" open={isThinkingStreaming}>
                <summary className="flex items-center gap-2 px-3 py-2 bg-amber-500/5 border border-amber-500/10 rounded-xl cursor-pointer hover:bg-amber-500/10 transition-all list-none select-none">
                  {isThinkingStreaming ? (
                    <Loader2 size={12} className="text-amber-500 animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500/40 flex-shrink-0" />
                  )}
                  <span className="text-[10px] font-bold tracking-widest uppercase text-amber-400/60">
                    {isThinkingStreaming ? "AI Reasoning (Thinking...)" : "AI Reasoning"}
                  </span>
                  <Plus size={10} className="ml-auto text-amber-400/40 group-open:rotate-45 transition-transform flex-shrink-0" />
                </summary>
                {/* max-h 효 overflow-y-auto: 길어지면 스크롤 / 자동 마지막 줄 스크롤 */}
                <div
                  ref={thoughtScrollRef}
                  className="mt-2 px-4 py-3 bg-amber-500/[0.02] border border-amber-500/5 rounded-xl text-[11px] text-slate-400/90 leading-relaxed font-medium italic thought-markdown markdown-content max-h-72 overflow-y-auto custom-scrollbar transition-all"
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                  >
                    {displayThinkingContent + (isThinkingStreaming ? " █" : "")}
                  </ReactMarkdown>
                </div>
              </details>
            )}

            {mainContent && (
              <div className="text-[11px] text-slate-300 leading-normal px-1 font-medium markdown-content pt-1 transition-all">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                >
                  {mainContent}
                </ReactMarkdown>
              </div>
            )}

            {msg.type === 'choice' && msg.data?.choices && (
              <div className="flex flex-col gap-2 mt-4 max-w-[95%]">
                {msg.data.choices.map((choice: any) => (
                  <button
                    key={choice.value}
                    onClick={() => onChoiceSelect?.(choice.value, msg.data?.originalMessage, msg.data?.design)}
                    className="flex flex-col items-start gap-1 px-4 py-3 bg-gradient-to-r from-purple-600/20 to-blue-600/20 border border-purple-500/40 rounded-xl hover:from-purple-600/30 hover:to-blue-600/30 transition-all active:scale-95 cursor-pointer"
                  >
                    <span className="text-[10px] font-bold text-purple-300">{choice.label}</span>
                    <span className="text-[9px] text-slate-400">{choice.description}</span>
                  </button>
                ))}
              </div>
            )}

          {msg.type === 'design' && (
            <div className="flex flex-col bg-white/[0.03] border border-blue-500/20 rounded-xl p-4 shadow-xl gap-3 backdrop-blur-md mb-4">
              <div className="flex items-center gap-2 text-blue-400">
                <FileCode2 size={14} />
                <span className="text-[10px] font-bold tracking-tight uppercase">전략 설계도</span>
                <span className="ml-auto text-[9px] text-slate-500">코드 생성 자동 진행 중...</span>
              </div>
              <div className="h-px bg-white/[0.05]" />
              <details className="group">
                <summary className="flex items-center gap-2 cursor-pointer list-none text-[10px] text-slate-400 hover:text-slate-200 transition-colors">
                  <Plus size={10} className="group-open:rotate-45 transition-transform" />
                  설계도 보기 / 접기
                </summary>
                <div className="mt-2 max-h-[200px] overflow-y-auto custom-scrollbar rounded-lg bg-black/40 border border-white/5 p-3">
                  <pre className="text-[10px] text-slate-300 font-mono leading-relaxed whitespace-pre-wrap break-all">
                    {msg.content}
                  </pre>
                </div>
              </details>
            </div>
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
  const [totalStages, setTotalStages] = useState(0);
  const [showStageProgress, setShowStageProgress] = useState(false);
  const [stageStartedAt, setStageStartedAt] = useState<number | null>(null);
  const [stageElapsedSeconds, setStageElapsedSeconds] = useState(0);
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
            type: (m.type === "analysis" ? "text" : (m.type === "design" ? "design" : (m.type || "text"))) as any,
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

  useEffect(() => {
    if (!isLoading || !stageStartedAt) {
      setStageElapsedSeconds(0);
      return;
    }
    const updateElapsed = () => {
      const elapsed = Math.max(0, Math.floor((Date.now() - stageStartedAt) / 1000));
      setStageElapsedSeconds(elapsed);
    };
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [isLoading, stageStartedAt]);

  const appendMessage = (message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  };

  // [UX] 메시지 개수가 변경되었을 때 즉, 내가 메시지를 치거나 새 블록이 생겼을 때 무조건 가장 아래로 강제 스크롤
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        virtuosoRef.current?.scrollToIndex({ 
          index: messages.length - 1, 
          align: 'end', 
          behavior: 'smooth' 
        });
      }, 50); // DOM 업데이트 대기 후 스크롤
    }
  }, [messages.length]);

  const handleShowCode = useCallback((code: string, title?: string, payload?: any) => {
    if (!code) return;
    if (onApplyCode) {
      onApplyCode(code, title, payload);
    }
  }, [onApplyCode]);

  const handleDesignCodeRequest = useCallback((designContent: string) => {
    const originalMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user" && m.content && m.content.trim())?.content;

    // API 호출 없이 choice UI만 바로 표시
    appendMessage({
      id: `${Date.now()}-choice`,
      role: "assistant",
      content: "",
      type: "choice",
      data: {
        choices: [
          { value: "loose",   label: "느슨하게 (코드만 바로 짜기)", description: "검증 기준 무시" },
          { value: "relaxed", label: "현실적 기준 (권장)",          description: "승률 35%, PF 1.05 등" },
          { value: "strict",  label: "엄격한 기준",                 description: "승률 45%, PF 1.20 등" },
        ],
        originalMessage,
        design: designContent,  // 설계 내용 직접 저장
      }
    });
  }, [appendMessage, messages]);

  const handleCodeGenModeChoice = useCallback(async (mode: string, originalMessage?: string, design?: string) => {
    // design이 있으면 (설계도 카드에서 직접 호출) context에 design 포함
    const newContext = { ...context, code_gen_mode: mode, ...(design ? { design } : {}) };

    // 원래 요청 메시지 사용 (design만 있을 경우엔 더미 메시지)
    const userMessage = originalMessage || (design ? "코드 생성" : "");
    if (!userMessage.trim()) return;

    setIsLoading(true);
    setCurrentStage(2);  // Stage 1은 이미 완료됨, Stage 2부터 시작
    setTotalStages(5);
    // loose 모드는 progress indicator 숨김 (빠른 코드 생성만 원함)
    setShowStageProgress(mode !== "loose");
    setStageStartedAt(Date.now());
    setStageElapsedSeconds(0);
    currentStageIdRef.current = "";
    setStatusText(mode === "loose" ? "⚙️ 코드 생성 중..." : "⚙️ Python 전략 코드 구현 중...");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const history = messages
        .filter((msg) =>
          msg.content &&
          msg.content.trim() &&
          !["choice", "design", "thought", "invocation", "strategy", "backtest"].includes(msg.type ?? "")
        )
        .map((msg) => ({ role: msg.role, content: msg.content }))
        .slice(-20);

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
          context: newContext,
          history,
        }),
        signal: controller.signal,
        cache: "no-store",
        timeoutMs: 0
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Stream reader not available");

      const decoder = new TextDecoder();
      let buffer = "";
      let shouldStop = false;

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

              case "progress":
                if (typeof event.label === "string" && event.label.trim()) {
                  setStatusText(event.label);
                }
                if (typeof event.stage === "number" && event.stage > 0) {
                  setCurrentStage(event.stage);
                }
                if (typeof event.elapsed_sec === "number" && Number.isFinite(event.elapsed_sec)) {
                  setStageElapsedSeconds(Math.max(0, Math.floor(event.elapsed_sec)));
                }
                break;

              case "stage":
                currentStageIdRef.current = `stage-${event.stage}-${Date.now()}`;
                setCurrentStage(event.stage);
                setStageStartedAt(Date.now());
                setStageElapsedSeconds(0);
                setStatusText(event.label ?? `단계 ${event.stage} 진행 중...`);
                break;

              case "thought":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
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

              case "analysis":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const stageId = currentStageIdRef.current;
                  const canAppend =
                    last &&
                    last.role === "assistant" &&
                    last.type === "text" &&
                    (stageId
                      ? last.id.startsWith(stageId)
                      : !last.id.includes("-invoke-") &&
                        !last.id.includes("-design") &&
                        !last.id.includes("-strategy") &&
                        !last.id.includes("-backtest"));

                  if (canAppend) {
                    const next = [...prev];
                    next[next.length - 1] = { ...last, content: last.content + event.content };
                    return next;
                  }

                  const newId = stageId
                    ? `${stageId}-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`
                    : `analysis-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
                  return [...prev, {
                    id: newId,
                    role: "assistant",
                    content: event.content,
                    type: "text",
                  }];
                });
                break;

              case "strategy":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const strategyMsg = {
                    id: `${Date.now()}-strategy`,
                    role: "assistant" as const,
                    content: "",
                    type: "strategy" as const,
                    data: event.data,
                  };
                  // 스트리밍 코드 텍스트 블록을 strategy 카드로 교체
                  if (last && last.role === "assistant" && last.type === "text") {
                    return [...prev.slice(0, -1), strategyMsg];
                  }
                  return [...prev, strategyMsg];
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
                    code: event.data.code || event.strategy_code,
                    payload: event.payload,
                  },
                });
                {
                  const finalCode = event.data.code || event.strategy_code;
                  if (finalCode && onApplyCode) {
                    onApplyCode(finalCode, event.data?.title || "Mined Strategy", event.payload);
                  }
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
                  data: { skill: event.skill, model: event.model, router_model: event.router_model, models: event.models },
                });
                setStatusText(`⚡ ${event.label || event.skill} 발동 중... ${event.model ? `(${event.model})` : ''}`);
                break;

              case "design":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const designMsg = {
                    id: `${Date.now()}-design`,
                    role: "assistant" as const,
                    content: event.content || "",
                    type: "design" as const,
                  };
                  if (last && last.role === "assistant" && last.type === "text") {
                    const next = [...prev];
                    next[next.length - 1] = { ...designMsg, id: last.id + "-design" };
                    return next;
                  }
                  return [...prev, designMsg];
                });
                break;

              case "error":
                appendMessage({
                  id: `${Date.now()}-pipeline-error`,
                  role: "assistant",
                  content: event.content || "파이프라인 실행 중 오류가 발생했습니다.",
                  type: "text",
                });
                setStatusText("❌ 파이프라인 오류");
                break;

              case "done":
                shouldStop = true;
                break;
            }
          } catch (err) {
            console.error("Event Parse Error:", err);
          }
        }

        if (shouldStop) break;
      }
    } catch (e) {
      console.error("Mode choice error:", e);
      const errorMessage = formatChatRunError(e);
      appendMessage({
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `코드 생성 재개 중 오류: ${errorMessage}`,
        type: "text",
      });
    } finally {
      setIsLoading(false);
      setStageStartedAt(null);
      setStageElapsedSeconds(0);
      abortControllerRef.current = null;
    }
  }, [messages, context, appendMessage, onApplyCode, onBacktestGenerated]);

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
    setTotalStages(0);
    setShowStageProgress(false);
    setStageStartedAt(Date.now());
    setStageElapsedSeconds(0);
    currentStageIdRef.current = "";
    setStatusText("AI 분석 중...");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // LLM에 보낼 히스토리: 너무 길면 Context Window 초과 위험이 있으므로 최근 15개로 제한
      const history = messages
        .filter((msg) =>
          msg.content &&
          msg.content.trim() &&
          !["choice", "design", "thought", "invocation", "strategy", "backtest"].includes(msg.type ?? "")
        )
        .map((msg) => ({ role: msg.role, content: msg.content }))
        .slice(-20);

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
        timeoutMs: 0
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Stream reader not available");

      const decoder = new TextDecoder();
      let buffer = "";
      let shouldStop = false;

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

              case "progress":
                if (typeof event.label === "string" && event.label.trim()) {
                  setStatusText(event.label);
                }
                if (typeof event.stage === "number" && event.stage > 0) {
                  setCurrentStage(event.stage);
                }
                if (typeof event.elapsed_sec === "number" && Number.isFinite(event.elapsed_sec)) {
                  setStageElapsedSeconds(Math.max(0, Math.floor(event.elapsed_sec)));
                }
                break;

              // stage 이벤트: 새 덩어리(블록) 시작을 강제함
              case "stage": {
                const newStageId = `stage-${event.stage}-${Date.now()}`;
                currentStageIdRef.current = newStageId;
                const stageNum = Number(event.stage) || 0;
                setCurrentStage(stageNum);
                setStageStartedAt(Date.now());
                setStageElapsedSeconds(0);
                // invocation 정보가 없는 승인 재요청(예/네) 케이스를 위한 fallback
                if (stageNum > 1 && !showStageProgress) {
                  setShowStageProgress(true);
                }
                if (stageNum > 0 && totalStages === 0) {
                  setTotalStages(stageNum >= 4 ? 5 : stageNum);
                }
                setStatusText(event.label ?? `단계 ${event.stage} 진행 중...`);

                // Stage 1: thinking이 올 것이므로 미리 message 생성
                if (stageNum === 1) {
                  appendMessage({
                    id: `thought-stage1-${Date.now()}`,
                    role: "assistant",
                    content: "",
                    type: "thought",
                  });
                }
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
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const strategyMsg = {
                    id: `${Date.now()}-strategy`,
                    role: "assistant" as const,
                    content: "",
                    type: "strategy" as const,
                    data: event.data,
                  };
                  // 스트리밍 코드 텍스트 블록을 strategy 카드로 교체
                  if (last && last.role === "assistant" && last.type === "text") {
                    return [...prev.slice(0, -1), strategyMsg];
                  }
                  return [...prev, strategyMsg];
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
                const stageMeta = SKILL_STAGE_META[event.skill] ?? { total: 0, showProgress: false };
                setTotalStages(stageMeta.total);
                setShowStageProgress(stageMeta.showProgress);
                appendMessage({
                  id: `${Date.now()}-invoke-${event.skill}`,
                  role: "assistant",
                  content: event.label || event.skill,
                  type: "invocation",
                  data: { skill: event.skill, model: event.model, router_model: event.router_model, models: event.models }
                });
                setStatusText(`⚡ ${event.label || event.skill} 발동 중... ${event.model ? `(${event.model})` : ''}`);
                break;

              case "design":
                // ✅ 직전 text 블록(설계도 스트리밍 누적본)을 design 카드로 교체
                // → analysis로 실시간 스트리밍 후 완성되면 카드로 변신 (이중 표시 없음)
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const designMsg = {
                    id: `${Date.now()}-design`,
                    role: "assistant" as const,
                    content: event.content || "",
                    type: "design" as const,
                  };
                  // 직전이 스트리밍 텍스트 블록이면 교체, 아니면 append
                  if (last && last.role === "assistant" && last.type === "text") {
                    const next = [...prev];
                    next[next.length - 1] = { ...designMsg, id: last.id + "-design" };
                    return next;
                  }
                  return [...prev, designMsg];
                });
                break;

              case "analysis":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  // 직전 메시지가 같은 스트리밍 텍스트 블록이면 이어 붙임
                  // stage 이벤트가 오면 currentStageIdRef가 바뀌므로 자연스럽게 새 블록 생성
                  const stageId = currentStageIdRef.current;
                  const canAppend =
                    last &&
                    last.role === "assistant" &&
                    last.type === "text" &&
                    (stageId ? last.id.startsWith(stageId) : !last.id.includes("-invoke-") && !last.id.includes("-design") && !last.id.includes("-strategy") && !last.id.includes("-backtest"));

                  if (canAppend) {
                    const next = [...prev];
                    next[next.length - 1] = { ...last, content: last.content + event.content };
                    return next;
                  }
                  // 새 stage이거나 직전이 다른 타입이면 새 블록 생성
                  const newId = stageId
                    ? `${stageId}-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`
                    : `analysis-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
                  return [...prev, {
                    id: newId,
                    role: "assistant",
                    content: event.content,
                    type: "text",
                  }];
                });
                break;

              case "choice": {
                // 코드 생성 모드 선택 - 원래 사용자 메시지 저장
                const originalMsg = messages
                  .filter(m => m.role === "user")
                  .filter(m => m.content && !m.content.includes("현재 시장 상황"))
                  .slice(-1)[0]?.content;
                appendMessage({
                  id: `${Date.now()}-choice`,
                  role: "assistant",
                  content: "",
                  type: "choice",
                  data: { choices: event.choices || [], originalMessage: originalMsg }
                });
                setStatusText("⏸️ 코드 생성 방식을 선택해주세요");
                break;
              }

              case "error":
                appendMessage({
                  id: `${Date.now()}-pipeline-error`,
                  role: "assistant",
                  content: event.content || "파이프라인 실행 중 오류가 발생했습니다.",
                  type: "text",
                });
                setStatusText("❌ 파이프라인 오류");
                break;

              case "done":
                shouldStop = true;
                break;
            }
          } catch (err) {
            console.error("Event Parse Error:", err, line);
          }
        }

        if (shouldStop) break;
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
      setStageStartedAt(null);
      setStageElapsedSeconds(0);
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
          followOutput="smooth"
          className="custom-scrollbar"
          alignToBottom
          itemContent={(index, msg) => (
            <div className="px-4">
              <MessageItem
                msg={msg}
                onShowCode={handleShowCode}
                onSendMessage={handleSend}
                isStreaming={index === messages.length - 1 && isLoading}
                onChoiceSelect={(choiceValue, originalMsg, design) => handleCodeGenModeChoice(choiceValue, originalMsg, design)}
                onDesignCodeRequest={handleDesignCodeRequest}
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
              <span className="text-[10px] font-bold text-slate-500 tabular-nums">
                {stageElapsedSeconds}초
              </span>
              {showStageProgress && totalStages > 1 && (
                <div className="flex gap-1.5 ml-auto items-center">
                  {Array.from({ length: totalStages }, (_, idx) => idx + 1).map((s) => (
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
              )}
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
