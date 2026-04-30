"use client";

import { useState, useRef, useEffect, useMemo, memo, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from 'rehype-raw';
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
import { Send, Plus, CheckCircle2, FileCode2, Loader2, Zap, Trash2, RotateCcw, MessageSquare, GitBranch, ChevronDown, Copy, Check, SlidersHorizontal } from "lucide-react";
import { fetchWithBypass } from "@/lib/api";
import OptimizationMiniPanel from "@/components/features/backtest/OptimizationMiniPanel";

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

// [UI] 커스텀 마크다운 코드 블록 (복사 버튼 포함)
interface CodeBlockProps {
  node?: any;
  inline?: boolean;
  className?: string;
  children: React.ReactNode;
  [key: string]: any;
}

const CodeBlock = ({ node, inline, className, children, ...props }: CodeBlockProps) => {
  const [copied, setCopied] = useState(false);
  const codeValue = String(children).replace(/\n$/, "");
  // language- 가 없거나 inline인 경우 버튼 제외
  const isInline = !!(inline || !className?.includes('language-'));

  const handleCopy = () => {
    navigator.clipboard.writeText(codeValue);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isInline) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }

  return (
    <div className="relative group/code">
      <button
        onClick={handleCopy}
        className="absolute right-3 top-3 p-2 rounded-lg bg-white/10 border border-white/10 text-slate-400 opacity-0 group-hover/code:opacity-100 hover:bg-white/20 hover:text-white transition-all z-20 backdrop-blur-md"
        title="코드 복사"
      >
        {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
      </button>
      <code className={className} {...props}>
        {children}
      </code>
    </div>
  );
};

const MarkdownComponents = {
  pre: ({ children }: { children: React.ReactNode }) => {
    return (
      <pre className="relative mb-4 last:mb-0 overflow-visible">
        {children}
      </pre>
    );
  },
  code: CodeBlock
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

  // thought 타입: 스트리밍 중 = 열림, 완료 후 = 자동 접힘
  if (msg.role === 'assistant' && msg.type === 'thought') {
    thinkingContent = (msg.content || "").replace(/<\/?(thought|think|think_process|reasoning)[^>]*>/gi, '').trim();
    mainContent = "";
  } else if (msg.role === 'assistant') {
    // text 타입 내 <think> 태그 파싱 (대소문자 무관, 공백 허용)
    const thoughtRegex = /<(thought|think|think_process|reasoning)>([\s\S]*?)(?:<\/\1>|$)/gi;
    const match = thoughtRegex.exec(msg.content || "");
    
    if (match) {
      thinkingContent = match[2].trim();
      mainContent = (msg.content || "").replace(match[0], "").trim();
    } else {
      mainContent = msg.content || "";
    }
  }

  isThinkingStreaming = !!isStreaming && !!thinkingContent;

  // 자동 스크롤: thought 컨텐츠 div ref
  const thoughtScrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (isThinkingStreaming && thoughtScrollRef.current) {
      thoughtScrollRef.current.scrollTop = thoughtScrollRef.current.scrollHeight;
    }
  });

  const displayThinkingContent = thinkingContent;

  return (
    <div className={`flex flex-col py-3 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
      {msg.role === 'user' ? (
        <div className="bg-purple-600/20 border border-purple-500/20 rounded-2xl px-4 py-2.5 max-w-[85%] text-[12px] text-purple-100 shadow-sm animate-in slide-in-from-right-2 duration-300 markdown-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
            components={MarkdownComponents}
          >
            {msg.content}
          </ReactMarkdown>
        </div>
      ) : (
        <div className="w-full space-y-4 animate-in fade-in duration-500">
            {msg.type === 'invocation' && (
              <div className="flex flex-col gap-1.5 mb-3">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-xl w-fit">
                  <Zap size={13} className="text-blue-400 fill-blue-400/20" />
                  <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">실행: {msg.content}</span>
                </div>
              </div>
            )}

            {thinkingContent && (
              <details className="group mb-1 max-w-[95%]" open={isThinkingStreaming}>
                <summary className="flex items-center gap-2 px-3 py-2 bg-white/[0.03] border border-white/[0.05] rounded-xl cursor-pointer hover:bg-white/[0.06] transition-all list-none select-none">
                  {isThinkingStreaming ? (
                    <Loader2 size={12} className="text-amber-500 animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500/40 flex-shrink-0" />
                  )}
                  <span className="text-[10px] font-bold tracking-widest uppercase text-amber-500/60 font-mono">
                    {isThinkingStreaming ? "AI Reasoning (Streaming...)" : "AI Reasoning"}
                  </span>
                  <Plus size={10} className="ml-auto text-white/20 group-open:rotate-45 transition-transform flex-shrink-0" />
                </summary>
                <div
                  ref={thoughtScrollRef}
                  className="mt-2 px-4 py-3 bg-black/20 border border-white/[0.03] rounded-xl font-medium italic markdown-content max-h-72 overflow-y-auto custom-scrollbar transition-all opacity-80 text-[11px] leading-relaxed pb-8"
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={MarkdownComponents}
                  >
                    {displayThinkingContent + (isThinkingStreaming ? " █" : "")}
                  </ReactMarkdown>
                </div>
              </details>
            )}

            {mainContent && (
              <div className={`text-[12px] text-slate-200 leading-relaxed px-1.5 markdown-content animate-in slide-in-from-left-1 duration-300 mb-4 ${
                mainContent.length < 60 && /^[A-Z][A-Za-z0-9_]+$/.test(mainContent.trim()) ? 'strategy-title-header' : 
                mainContent.length < 100 && mainContent.includes('|') ? 'metadata-summary-badge' : ''
              }`}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                  components={MarkdownComponents}
                >
                  {mainContent}
                </ReactMarkdown>
              </div>
            )}

            {/* choice 메시지 타입 렌더링 제거 (자동 진행 방식으로 변경됨) */}

          {msg.type === 'design' && (
            <div className="flex flex-col bg-white/[0.03] border border-blue-500/20 rounded-xl p-5 shadow-2xl gap-4 backdrop-blur-md mb-8 mx-1">
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
            <div className="flex flex-col bg-white/[0.03] border border-white/[0.08] rounded-xl p-4 shadow-2xl gap-3 backdrop-blur-md mb-8 mx-1">
              <div className="flex items-center gap-2 text-[#4ade80]">
                <CheckCircle2 size={18} />
                <span className="text-xs font-bold tracking-tight uppercase">전략 생성 완료</span>
              </div>
              <div className="h-px bg-white/[0.05] my-2" />
              <div className="space-y-3 my-2">
                <h3 className="text-[13px] font-black text-white px-1">{msg.data.title}</h3>
                <p className="text-[11px] text-slate-400 leading-relaxed italic font-medium px-1">
                  {msg.data.description}
                </p>
                
                {msg.data.code && (
                  <div className="mt-4 rounded-lg bg-black/40 border border-white/5 p-2 overflow-hidden relative group/stratcode">
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(String(msg.data.code));
                        // UI 피드백은 생략하거나 버튼 상태 관리를 위해 별도 컴포넌트화 필요하지만, 우선 기본 복사 기능 우선 적용
                      }}
                      className="absolute right-2 top-2 p-1.5 rounded-md bg-white/5 border border-white/10 text-slate-400 opacity-0 group-hover/stratcode:opacity-100 hover:bg-white/10 hover:text-white transition-all z-10"
                      title="코드 복사"
                    >
                      <Copy size={12} />
                    </button>
                    <div className="max-h-[80px] overflow-y-auto overflow-x-auto custom-scrollbar">
                      <pre className="text-[10px] text-purple-200/60 font-mono leading-tight break-normal whitespace-pre">
                        {msg.data.code}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
              <button
                onClick={() => onShowCode(String(msg.data?.code || ""), msg.data?.title, msg.data?.backtest_payload)}
                className="flex items-center justify-center gap-2 w-full px-4 py-1.5 bg-purple-600/10 border border-purple-500/30 rounded-xl text-[10px] font-bold text-purple-100 hover:bg-purple-600/20 transition-all active:scale-95"
              >
                <FileCode2 size={12} />
                전략 코드 에디터에 적용
              </button>
            </div>
          )}

          {msg.type === 'backtest' && (
            <div className="flex flex-col bg-white/[0.03] border border-white/[0.08] rounded-xl gap-3 p-4 shadow-2xl backdrop-blur-md mb-8 mx-1">
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
  const [panelMode, setPanelMode] = useState<"pipeline" | "chat" | "optimize">("pipeline");
  const [chatModel, setChatModel] = useState("deepseek-v4-flash");
  const [showModelSelect, setShowModelSelect] = useState(false);
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
      const text = await res.text();
      if (!text || !res.ok) return;
      const data = JSON.parse(text);
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
        const text = await res.text();
        if (!text) return;
        const data = JSON.parse(text);
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

  useEffect(() => {
    if (!showModelSelect) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-model-select]')) setShowModelSelect(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showModelSelect]);

  const handleShowCode = useCallback((code: string, title?: string, payload?: any) => {
    if (!code) return;
    if (onApplyCode) {
      onApplyCode(code, title, payload);
    }
  }, [onApplyCode]);

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
            if (!raw || raw === "[DONE]") continue;
            if (!raw.startsWith("{")) continue; 
            
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
  }, [messages, context, appendMessage, onApplyCode, onBacktestGenerated, sessionIdRef, setIsLoading, setStatusText, setCurrentStage, setTotalStages, setShowStageProgress, setStageStartedAt, setStageElapsedSeconds]);

  const handleDesignCodeRequest = useCallback((designContent: string) => {
    const originalMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user" && m.content && m.content.trim())?.content;

    // 선택창 없이 바로 'relaxed' 모드로 코드 생성 시작
    handleCodeGenModeChoice("relaxed", originalMessage, designContent);
  }, [handleCodeGenModeChoice, messages]);

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
          force_chat_mode: panelMode === "chat",
          ...(panelMode === "chat" && { chat_model: chatModel }),
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
    <div className="flex flex-col h-full bg-background/20">
      {/* 🆔 헤더 세션 컨트롤 바 */}
      <div className="px-4 py-3 border-b border-white/[0.05] bg-background/40 backdrop-blur-md flex items-center justify-between gap-3">
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
        {panelMode === "optimize" ? (
          <div className="h-full overflow-y-auto no-scrollbar p-2">
            <OptimizationMiniPanel
              symbol={String(context?.symbol || "BTCUSDT")}
              timeframe={String(context?.timeframe || "1h")}
              startDate={String(context?.start_date || "")}
              endDate={String(context?.end_date || "")}
              strategy={String(context?.strategy || context?.strategy_title || "custom")}
              strategyCode={String(context?.editor_code || context?.current_strategy?.code || "")}
              busy={isLoading}
              onApplyOptimizedCode={(code, payload) => {
                if (onApplyCode) {
                  onApplyCode(code, String(context?.strategy_title || context?.strategy || "Optimized Strategy"), payload);
                }
                if (payload && onBacktestGenerated) {
                  onBacktestGenerated(payload);
                }
              }}
            />
          </div>
        ) : (
          <Virtuoso
            ref={virtuosoRef}
            data={messages}
            followOutput="smooth"
            className="custom-scrollbar"
            alignToBottom
            itemContent={(index: number, msg: ChatMessage) => (
              <div className="px-4">
                <MessageItem
                  msg={msg}
                  onShowCode={handleShowCode}
                  onSendMessage={handleSend}
                  isStreaming={index === messages.length - 1 && isLoading}
                  onChoiceSelect={(choiceValue: string, originalMsg: ChatMessage, design?: any) => handleCodeGenModeChoice(choiceValue, originalMsg, design)}
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
              ),
              Footer: () => <div className="h-0 pointer-events-none" />
            }}
          />
        )}
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

          {/* Mode Toggle + Model Selector */}
          <div className="flex items-center gap-2 px-1">
            {/* Pipeline / Chat 모드 토글 */}
            <div className="flex items-center rounded-sm bg-white/[0.04] border border-white/[0.06] p-0.5 gap-0.5 font-mono">
              <button
                onClick={() => setPanelMode("pipeline")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-sm text-[10px] font-bold uppercase transition-all duration-200 ${
                  panelMode === "pipeline"
                    ? 'bg-purple-600/40 text-purple-100 border border-purple-500/50 shadow-[0_0_10px_rgba(168,85,247,0.2)]'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <GitBranch size={10} />
                PIPELINE
              </button>
              <button
                onClick={() => setPanelMode("chat")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-sm text-[10px] font-bold uppercase transition-all duration-200 ${
                  panelMode === "chat"
                    ? 'bg-white/10 text-white border border-white/20'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <MessageSquare size={10} />
                CHAT
              </button>
              <button
                onClick={() => setPanelMode("optimize")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-sm text-[10px] font-bold uppercase transition-all duration-200 ${
                  panelMode === "optimize"
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.15)]'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <SlidersHorizontal size={10} />
                OPTIMIZE
              </button>
            </div>

            {/* 모델 셀렉터 (Chat 모드일 때만 표시) */}
            {panelMode === "chat" && (
              <div className="relative" data-model-select>
                <button
                  onClick={() => setShowModelSelect(v => !v)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-white/[0.04] border border-white/[0.06] text-[11px] font-mono text-slate-400 hover:text-slate-200 hover:border-white/[0.12] transition-all duration-200"
                >
                  {chatModel}
                  <ChevronDown size={10} className={`transition-transform duration-200 ${showModelSelect ? 'rotate-180' : ''}`} />
                </button>
                {showModelSelect && (
                  <div className="absolute bottom-full mb-1.5 left-0 z-50 bg-background border border-white/[0.1] rounded-xl shadow-2xl overflow-hidden min-w-[200px] py-1">
                    {[
                      "deepseek-v4-flash",
                      "deepseek-v4-pro",
                      "minimax-m2.5",
                      "deepseek-v3.1-terminus"
                    ].map(m => (
                    <button
                      key={m}
                      onClick={() => { setChatModel(m); setShowModelSelect(false); }}
                      className={`w-full text-left px-3 py-2.5 text-[11px] font-mono transition-all duration-200 ${
                        chatModel === m
                          ? 'bg-white/[0.08] text-white'
                          : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="truncate flex-1">{m}</span>
                        {m === "minimax-m2.5" && <span className="shrink-0 px-1.5 py-0.5 rounded-md bg-purple-500/10 text-[9px] text-purple-400 font-sans whitespace-nowrap">핵심</span>}
                        {m === "deepseek-v4-flash" && <span className="shrink-0 px-1.5 py-0.5 rounded-md bg-green-500/10 text-[9px] text-green-400 font-sans whitespace-nowrap">⭐ 최고속</span>}
                        {m === "minimax-m2.5" && <span className="shrink-0 px-1.5 py-0.5 rounded-md bg-purple-500/10 text-[9px] text-purple-400 font-sans whitespace-nowrap">안정</span>}
                        {m === "deepseek-v3.1-terminus" && <span className="shrink-0 px-1.5 py-0.5 rounded-md bg-blue-500/10 text-[9px] text-blue-400 font-sans whitespace-nowrap">강력</span>}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            )}
          </div>

          {/* Integrated Input Bar */}
          {panelMode !== "optimize" && (
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
          )}
        </div>
      </div>
    </div>
  );
}

function StatItem({ label, value, color = "text-white" }: { label: string, value: string, color?: string }) {
  return (
    <div className="space-y-0.5">
      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-tight leading-none">{label}</div>
      <div className={`text-[12px] font-black tracking-tight ${color}`}>{value}</div>
    </div>
  );
}
