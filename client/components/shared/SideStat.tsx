import { cn } from "@/lib/utils";

interface SideStatProps {
  label: string;
  value: string;
  note?: string;
  noteColor?: string;
}

export function SideStat({ label, value, note, noteColor }: SideStatProps) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 flex flex-col gap-0.5 hover:bg-white/[0.08] transition-colors">
      <div className="font-mono text-[8px] tracking-[0.2em] text-muted-foreground uppercase">{label}</div>
      <div className="font-mono text-[11px] font-bold text-foreground/90 truncate">{value}</div>
      {note && (
        <div className={cn("font-mono text-[9px] font-medium opacity-80", noteColor || "text-muted-foreground")}>
          {note}
        </div>
      )}
    </div>
  );
}
