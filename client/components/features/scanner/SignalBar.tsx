export function SignalBar({ label, value, note, color }: { label: string; value: number; note?: string; color: string }) {
  return (
    <div className="flex flex-col gap-1.5 p-2.5 bg-white/[0.02] border border-white/10 rounded-lg hover:bg-white/[0.04] transition-colors">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[8px] tracking-[0.14em] text-slate-400 uppercase">{label}</span>
        <span className="font-mono text-[10px] font-semibold text-slate-200">{value.toFixed(0)}%</span>
      </div>
      <div className="h-1 bg-white/5 rounded-full overflow-hidden">
        <div className="h-full transition-all duration-700" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
      {note && <div className="text-[9px] text-slate-500 leading-tight truncate">{note}</div>}
    </div>
  );
}
