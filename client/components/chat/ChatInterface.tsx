"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from 'rehype-raw';
import { Send, Plus, CheckCircle2, FileCode2, Loader2, Zap } from "lucide-react";
import { fetchWithBypass } from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  type?: "text" | "strategy" | "backtest" | "thought";
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

// Removed TypewriterText components to eliminate artificial latency.

export default function ChatInterface({ context = {}, onBacktestGenerated, onApplyCode }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState("AI 분석 중...");
  const [currentStage, setCurrentStage] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  // stage 이벤트마다 새 블록을 강제 시작하기 위한 key
  const currentStageIdRef = useRef<string>("");

  // 🆔 세션 ID 관리 (localStorage 유지)
  const sessionIdRef = useRef<string>("");
  useEffect(() => {
    let sid = localStorage.getItem("chat_session_id");
    if (!sid) {
      sid = `session-${Math.random().toString(36).substr(2, 9)}-${Date.now()}`;
      localStorage.setItem("chat_session_id", sid);
    }
    sessionIdRef.current = sid;

    // 과거 기록 불러오기
    const loadHistory = async () => {
      try {
        const currentHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
        const backendBase = process.env.NEXT_PUBLIC_API_URL 
          ? process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "")
          : (currentHost === 'localhost' || currentHost === '127.0.0.1') 
            ? "http://localhost:8000" 
            : ""; // Relative path will use Next.js rewrite
        
        const res = await fetch(`${backendBase}/api/chat/history?session_id=${sid}`, {
          headers: {
            "ngrok-skip-browser-warning": "true",
            "Bypass-Tunnel-Reminder": "true"
          }
        });
        const data = await res.json();
        if (data.success && data.messages) {
          // DB 포맷을 ChatMessage 포맷으로 변환
          const historyMessages: ChatMessage[] = data.messages.map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content || "",
            type: m.type as any,
            data: m.data
          }));
          setMessages(historyMessages);
        }
      } catch (err) {
        console.error("History load failed:", err);
      }
    };
    loadHistory();
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

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

  const handleShowCode = (code: string, title?: string, payload?: any) => {
    if (!code) return;
    // Apply to editor AND results
    if (onApplyCode) {
      onApplyCode(code, title, payload);
    }
  };

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
    setStatusText("AI 분석 중...");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const history = messages
        .filter((msg) => msg.content && msg.content.trim())
        .map((msg) => ({
          role: msg.role,
          content: msg.content,
        }));

      // 🚀 Next.js 프록시 버퍼링을 피하기 위해 가급적 백엔드로 직접 요청
      const currentHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
      const backendBase = process.env.NEXT_PUBLIC_API_URL 
        ? process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "")
        : (currentHost === 'localhost' || currentHost === '127.0.0.1') 
          ? "http://localhost:8000" 
          : ""; // 비로컬 환경에서는 상대 경로(/api/...)를 통해 Next.js 리라이트 활용
      const url = `${backendBase}/api/chat/run?t=${Date.now()}`;

      const response = await fetch(url, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Cache-Control": "no-cache",
          "Pragma": "no-cache",
          "ngrok-skip-browser-warning": "true",
          "Bypass-Tunnel-Reminder": "true"
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionIdRef.current,
          context,
          history,
        }),
        signal: controller.signal,
        cache: "no-store" // [중요] 브라우저 캐시 무시
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
                  // 같은 stage의 thought면 이어 붙임, 아니면 새 블록
                  if (last && last.role === "assistant" && last.type === "thought" && last.id.startsWith(stageId)) {
                    const next = [...prev];
                    next[next.length - 1] = { ...last, content: last.content + event.content };
                    return next;
                  }
                  return [...prev, {
                    id: `${stageId}-thought`,
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
                    code: event.strategy_code,
                    payload: event.payload
                  },
                });
                
                // [NEW] 백테스트 완료 시 발굴된 코드를 에디터에 즉시 자동 적용
                if (event.strategy_code && onApplyCode) {
                  onApplyCode(event.strategy_code, event.data?.title || "Mined Strategy", event.payload);
                }
                
                if (event.payload && onBacktestGenerated) {
                  onBacktestGenerated(event.payload);
                }
                break;

              case "analysis":
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const stageId = currentStageIdRef.current;
                  // 같은 stage의 analysis 메시지면 이어 붙임
                  if (last && last.role === "assistant" && last.type === "text" && last.id.startsWith(stageId)) {
                    const next = [...prev];
                    next[next.length - 1] = { ...last, content: last.content + event.content };
                    return next;
                  }
                  // 새 stage이거나 직전이 다른 타입이면 새 블록 생성
                  return [...prev, {
                    id: `${stageId}-${Date.now()}-analysis`,
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
      appendMessage({
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `전략 생성/백테스트 실행 중 오류가 발생했습니다.\n사유: ${errorMessage}`,
        type: "text",
      });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#060912]/20">
      {/* Chat Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 flex flex-col gap-y-3 custom-scrollbar"
      >
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col gap-3 items-center justify-center h-full space-y-4 opacity-80 py-10">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center border border-purple-500/20 mb-2">
              <Zap size={24} className="text-purple-400 animate-pulse" />
            </div>
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Get Started with AI Strategy</h3>
            <div className="flex flex-col gap-2 w-full max-w-sm">
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

        {messages.map((msg) => (
          <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            {msg.role === 'user' ? (
              <div className="bg-purple-600/20 border border-purple-500/20 rounded-2xl px-4 py-2 max-w-[85%] text-sm text-purple-100">
                {msg.content}
              </div>
            ) : (
              <div className="w-full space-y-4">
                {msg.role === 'assistant' && msg.type === 'text' && (
                  <div className="text-[11px] text-slate-400/90 leading-normal px-1 font-medium markdown-content pt-1 transition-all duration-300">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                    >
                      {msg.content}
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
                    <div className="mt-2 px-4 py-3 bg-amber-500/[0.02] border border-amber-500/5 rounded-xl text-[11px] text-slate-400/90 leading-relaxed font-medium italic thought-markdown markdown-content overflow-hidden animate-in fade-in slide-in-from-top-1 duration-200">
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeRaw]}
                      >
                        {msg.content.replace(/<\/?thought>/gi, '')}
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
                      
                      {/* 📝 코드 미리보기 - 상시 노출 (디폴트) */}
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
                      onClick={() => handleShowCode(String(msg.data?.code || ""), msg.data?.title, msg.data?.backtest_payload)}
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
                    
                    {/* 📝 수동 재적용 버튼 (편의성) */}
                    <button
                      onClick={() => handleShowCode(String(msg.data?.code || ""), "Mined Strategy", msg.data?.payload)}
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
        ))}
        {isLoading && (
          <div className="flex flex-col items-start gap-2">
            {/* 단계 진행 표시 */}
            {currentStage > 0 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-purple-500/10 border border-purple-500/20">
                {[1,2,3,4,5].map((s) => (
                  <div key={s} className={`w-1.5 h-1.5 rounded-full transition-all duration-500 ${
                    s < currentStage ? 'bg-purple-400' :
                    s === currentStage ? 'bg-purple-300 animate-pulse scale-125' :
                    'bg-slate-700'
                  }`} />
                ))}
                <span className="text-[10px] text-purple-300 font-bold ml-1">{currentStage}/5</span>
              </div>
            )}
            <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl px-4 py-2 flex items-center gap-2 animate-pulse">
              <Loader2 size={14} className="animate-spin text-purple-400" />
              <span className="text-xs text-slate-500 font-medium tracking-tight">{statusText}</span>
            </div>
          </div>
        )}
      </div>

      {/* Chat Input */}
      <div className="p-4 bg-[#0a0f1d]/80 backdrop-blur-xl border-t border-white/[0.05]">
        <div className="relative flex items-center bg-white/[0.03] border border-white/[0.1] rounded-2xl p-2 transition-all focus-within:border-purple-500/30 focus-within:bg-white/[0.05] shadow-inner">
          <button className="p-2.5 text-slate-500 hover:text-slate-300 transition-colors">
            <Plus size={20} />
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="전략에 대해 질문하세요..."
            className="flex-1 bg-transparent border-none focus:ring-0 text-sm text-slate-200 placeholder:text-slate-600 resize-none py-2.5 px-2 max-h-32 overflow-y-auto custom-scrollbar"
            rows={1}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            className={`p-2.5 rounded-xl transition-all ${input.trim() && !isLoading ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/20' : 'text-slate-600 cursor-not-allowed'}`}
          >
            <Send size={18} />
          </button>
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
