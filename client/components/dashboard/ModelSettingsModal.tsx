"use client";

import { X, Settings2, Save, RotateCcw, MessagesSquare, Zap, Check } from "lucide-react";
import { useState, useEffect } from "react";
import { fetchWithBypass } from "@/lib/api";

interface ModelSettings {
  chat_provider: string;
  chat_model: string;
  chat_base_url: string;
  evo_base_url: string;
  evo_model: string;
  evo_api_key: string;
}

import { useModalStore } from "@/store/useModalStore";

const CHAT_MODELS = [
  { id: "gpt-oss:120b-cloud", name: "GPT-OSS 120B", desc: "고성능 로컬 추론" },
  { id: "llama3.3:70b", name: "Llama 3.3 70B", desc: "밸런스형 진화" },
  { id: "deepseek-v3", name: "DeepSeek V3", desc: "코딩 최적화" }
];

const EVO_MODELS = [
  { id: "qwen/qwen3.5-397b-a17b", name: "Qwen 3.5 397B", desc: "최강의 추론 (200K)", color: "text-purple-400" },
  { id: "meta/llama-3.1-405b", name: "Llama 3.1 405B", desc: "초거대 모델 (131K)", color: "text-blue-400" },
  { id: "meta/llama-3.3-70b-instruct", name: "Llama 3.3 70B", desc: "빠른 반복 (131K)", color: "text-indigo-400" },
  { id: "mistralai/mistral-large-2-2407", name: "Mistral Large 2", desc: "전통의 퀀트 (131K)", color: "text-emerald-400" },
  { id: "google/gemma-2-27b-it", name: "Gemma 2 27B", desc: "경량 고효율 (8K)", color: "text-orange-400" }
];

export default function ModelSettingsModal() {
  const { isOpen, close } = useModalStore();
  const onClose = close;

  const [settings, setSettings] = useState<ModelSettings>({
    chat_provider: "ollama",
    chat_model: "",
    chat_base_url: "",
    evo_base_url: "",
    evo_model: "",
    evo_api_key: "",
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const res = await fetchWithBypass("/api/system/settings");
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch (err) {
      console.error("Failed to fetch settings:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetchWithBypass("/api/system/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: "success", text: "성공적으로 반영되었습니다." });
        setTimeout(() => setMessage(null), 3000);
      } else {
        setMessage({ type: "error", text: data.detail || "저장에 실패했습니다." });
      }
    } catch (err) {
      setMessage({ type: "error", text: "서버 통신 중 오류가 발생했습니다." });
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 md:p-8">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-300"
        onClick={onClose}
      />
      
      {/* Modal Content */}
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-[#0c1221]/80 backdrop-blur-2xl border border-white/10 rounded-3xl shadow-[0_25px_70px_rgba(0,0,0,0.5)] flex flex-col animate-in zoom-in-95 duration-200 overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-5 border-b border-white/10 bg-gradient-to-r from-blue-600/20 via-purple-600/15 to-indigo-600/20 shrink-0">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/40">
              <Settings2 size={22} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-black text-white tracking-tight">AI Engine Config</h2>
              <p className="text-[10px] font-extrabold text-blue-400/80 uppercase tracking-[0.2em] mt-0.5">모델 엔진 및 추론 레이어 설정</p>
            </div>
          </div>

          <button 
            onClick={onClose}
            className="p-2 rounded-xl bg-white/5 border border-white/10 text-slate-500 hover:bg-white/10 hover:text-white transition-all shadow-inner"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar min-h-0">
          
          {/* Chat Section */}
          <section className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
                  <MessagesSquare size={16} />
                </div>
                <h3 className="text-xs font-black text-white uppercase tracking-widest">Dashboard Brain</h3>
              </div>
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter bg-white/5 px-2 py-0.5 rounded">Chat Interface</span>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase ml-1">Provider</label>
                <select 
                  value={settings.chat_provider}
                  onChange={(e) => setSettings({...settings, chat_provider: e.target.value})}
                  className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2 text-sm text-white focus:outline-none transition-colors cursor-pointer"
                >
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openai">OpenAI (NIM Proxy)</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase ml-1">Current Model</label>
                <input 
                  type="text"
                  value={settings.chat_model}
                  onChange={(e) => setSettings({...settings, chat_model: e.target.value})}
                  className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2 text-sm text-white focus:outline-none transition-colors"
                />
              </div>
            </div>
            
            {/* Chat Model Selector Chips */}
            <div className="flex flex-wrap gap-2">
              {CHAT_MODELS.map(m => (
                <button
                  key={m.id}
                  onClick={() => setSettings({...settings, chat_model: m.id})}
                  className={`px-3 py-1.5 rounded-lg border text-[10px] font-bold transition-all ${
                    settings.chat_model === m.id 
                    ? 'bg-blue-600/20 border-blue-500/50 text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.2)]' 
                    : 'bg-white/5 border-white/5 text-slate-500 hover:bg-white/10 hover:text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {m.name}
                    {settings.chat_model === m.id && <Check size={10} />}
                  </div>
                </button>
              ))}
            </div>
          </section>

          <div className="h-px bg-white/5" />

          {/* Evolution Section */}
          <section className="space-y-5">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  <Zap size={16} />
                </div>
                <h3 className="text-xs font-black text-white uppercase tracking-widest">Evolution Engine</h3>
              </div>
               <span className="text-[10px] text-indigo-500 font-bold uppercase tracking-tighter bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/10">NIM Proxy Mode</span>
            </div>
            
            <div className="space-y-3">
              <label className="text-[10px] font-bold text-slate-500 uppercase ml-1">Select Evolutionary Brain</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {EVO_MODELS.map(m => (
                  <button
                    key={m.id}
                    onClick={() => setSettings({...settings, evo_model: m.id})}
                    className={`relative p-3 rounded-xl border text-left transition-all group ${
                      settings.evo_model === m.id 
                      ? 'bg-indigo-600/10 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.15)]' 
                      : 'bg-white/5 border-white/5 hover:bg-white/[0.08] hover:border-white/10'
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <div className={`text-[11px] font-black ${m.color} tracking-tight`}>{m.name}</div>
                        <div className="text-[10px] text-slate-500 font-medium">{m.desc}</div>
                      </div>
                      {settings.evo_model === m.id && (
                        <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center text-white scale-110 shadow-lg shadow-indigo-500/30">
                          <Check size={12} />
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
               <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase ml-1">Proxy EndPoint</label>
                  <input 
                    type="text"
                    value={settings.evo_base_url}
                    onChange={(e) => setSettings({...settings, evo_base_url: e.target.value})}
                    className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2 text-[11px] text-white focus:outline-none transition-colors font-mono"
                  />
               </div>
               <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase ml-1">Proxy API Key</label>
                  <input 
                    type="password"
                    value={settings.evo_api_key}
                    onChange={(e) => setSettings({...settings, evo_api_key: e.target.value})}
                    placeholder="sk-dummy"
                    className="w-full bg-white/[0.03] border border-white/10 rounded-lg px-4 py-2 text-sm text-white focus:outline-none transition-colors"
                  />
               </div>
            </div>
          </section>

          {message && (
            <div className={`p-4 rounded-2xl border flex items-center gap-3 animate-in slide-in-from-top-3 duration-300 ${
              message.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
            }`}>
              <div className={`w-2 h-2 rounded-full ${message.type === 'success' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'}`} />
              <span className="text-[11px] font-bold tracking-tight">{message.text}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-8 py-5 border-t border-white/5 bg-white/[0.02] flex items-center justify-between shrink-0 rounded-b-3xl">
          <button 
            onClick={fetchSettings}
            disabled={loading || saving}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/5 text-[10px] font-bold text-slate-500 hover:bg-white/10 hover:text-slate-300 transition-all disabled:opacity-50"
          >
            <RotateCcw size={14} className={loading ? "animate-spin" : ""} />
            초기화
          </button>
          
          <button 
            onClick={handleSave}
            disabled={saving || loading}
            className="flex items-center gap-3 px-6 py-2.5 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 shadow-xl shadow-blue-500/20 hover:from-blue-500 hover:to-indigo-500 text-white text-[11px] font-black tracking-wider transition-all disabled:opacity-50 group"
          >
            {saving ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save size={16} className="group-hover:scale-110 transition-transform" />
            )}
            {saving ? "저장 중..." : "설정 저장 및 즉시 반영"}
          </button>
        </div>
      </div>
    </div>
  );
}
