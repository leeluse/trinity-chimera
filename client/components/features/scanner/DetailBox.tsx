export function DetailBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white/[0.03] border border-white/5 p-3 rounded-lg flex flex-col gap-1 hover:border-white/10 transition-all">
      <div className="font-mono text-[8px] tracking-[0.2em] text-slate-500 uppercase">{label}</div>
      <div className="font-mono text-[11px] font-bold text-slate-200 truncate tracking-tight">{value}</div>
    </div>
  );
}
