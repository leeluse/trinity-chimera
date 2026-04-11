"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Plus, CheckCircle2, FileCode2, Loader2, Zap } from "lucide-react";
import { fetchWithBypass } from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  type?: "text" | "strategy" | "backtest";
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

const TypewriterText = ({ text, speed = 10 }: { text: string; speed?: number }) => {
  const [displayedText, setDisplayedText] = useState("");
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (index < text.length) {
      const timeout = setTimeout(() => {
        setDisplayedText((prev) => prev + text[index]);
        setIndex((prev) => prev + 1);
      }, speed);
      return () => clearTimeout(timeout);
    }
  }, [index, text, speed]);

  return (
    <div className="text-sm text-slate-300 leading-relaxed px-1 font-medium markdown-content pt-2 transition-all duration-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayedText}</ReactMarkdown>
    </div>
  );
};

export default function ChatInterface({ context = {}, onBacktestGenerated, onApplyCode }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

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

    const userMessage = raw.trim();
    const newUserMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: userMessage
    };

    appendMessage(newUserMsg);
    setInput("");
    setIsLoading(true);

    try {
      appendMessage({
        id: `${Date.now()}-ack`,
        role: "assistant",
        content: "지금 바로 전략을 구축하겠습니다. 코드를 생성하고 백테스트를 실행합니다.",
        type: "text",
      });

      const history = messages
        .filter((msg) => msg.content && msg.content.trim())
        .map((msg) => ({
          role: msg.role,
          content: msg.content,
        }));

      const res = await fetchWithBypass("/api/backtest/chat-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          context,
          history,
        })
      });

      if (!res.ok) throw new Error("Chat request failed");

      const data = await res.json();

      if (data?.strategy_card) {
        appendMessage({
          id: `${Date.now()}-strategy`,
          role: "assistant",
          content: "",
          type: "strategy",
          data: data.strategy_card,
        });
      }

      if (data?.backtest_card) {
        appendMessage({
          id: `${Date.now()}-backtest-${Math.random().toString(36).substr(2, 5)}`,
          role: "assistant",
          content: "",
          type: "backtest",
          data: data.backtest_card,
        });
      }

      if (data?.analysis) {
        appendMessage({
          id: `${Date.now()}-analysis`,
          role: "assistant",
          content: String(data.analysis),
          type: "text",
        });
      }

      if (data?.backtest_payload && onBacktestGenerated) {
        onBacktestGenerated(data.backtest_payload);
      }
    } catch (e) {
      console.error(e);
      appendMessage({
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "전략 생성/백테스트 실행 중 오류가 발생했습니다.",
        type: "text",
      });
    } finally {
      setIsLoading(false);
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
                {msg.type === 'text' && (
                  <TypewriterText text={msg.content} />
                )}

                {msg.type === 'strategy' && (
                  <div className="flex flex-col bg-white/[0.03] border border-white/[0.08] rounded-xl p-4 shadow-xl gap-3 backdrop-blur-md mb-6">
                    <div className="flex items-center gap-2 text-[#4ade80]">
                      <CheckCircle2 size={18} />
                      <span className="text-xs font-bold tracking-tight uppercase">전략 생성 완료</span>
                    </div>
                    <div className="h-px bg-white/[0.05] my-3" />
                    <div className="space-y-2">
                      <h3 className="text-sm font-bold text-white/90">{msg.data.title}</h3>
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-3 italic font-medium">
                        {msg.data.description}
                      </p>
                    </div>
                    <button
                      onClick={() => handleShowCode(String(msg.data?.code || ""), msg.data?.title, msg.data?.backtest_payload)}
                      className="flex items-center gap-2 px-4 py-2 bg-purple-600/20 border border-purple-500/40 rounded-xl text-[11px] font-bold text-purple-100 hover:bg-purple-600/30 transition-all active:scale-95 animate-pulse"
                    >
                      <FileCode2 size={14} />
                      에디터 및 결과 적용하기
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
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="flex items-start gap-2 animate-pulse">
            <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl px-4 py-2 flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-purple-400" />
              <span className="text-xs text-slate-500 font-medium tracking-tight">AI 분석 중...</span>
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
