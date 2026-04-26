export function SignalBar({ label, value, note, color }: { label: string; value: number; note?: string; color: string }) {
  return (
    <div className="flex flex-col gap-1.5 p-3 bg-white/[0.03] border border-white/5 rounded-lg hover:bg-white/[0.06] transition-colors">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] tracking-widest text-slate-400 uppercase">{label}</span>
        <span className="font-mono text-[10px] font-bold text-slate-200">{value.toFixed(0)}%</span>
      </div>
      <div className="h-1 bg-white/5 rounded-full overflow-hidden">
        <div className="h-full transition-all duration-700" style={{ width: `${value}%`, backgroundColor: color, boxShadow: `0 0 10px ${color}44` }} />
      </div>
      {note && <div className="text-[9px] text-slate-500 font-medium leading-tight truncate">{note}</div>}
    </div>
  );
}
