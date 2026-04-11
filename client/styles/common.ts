import { colors } from "./tokens";

export const cardClass = "bg-[#060912]/40 backdrop-blur-sm border border-white/[0.05] rounded-xl";
export const inputClass = `bg-white/[0.03] border border-white/10 text-slate-200 focus:border-[${colors.brand.primary}]/40 rounded-xl p-2.5 text-sm outline-none w-full transition-all`;
export const glassClass = "backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl shadow-2xl";

export const ambientGlows = {
  blue: `absolute top-[10%] left-[10%] w-[400px] h-[400px] bg-[${colors.brand.indigo}]/10 blur-[120px] rounded-full pointer-events-none`,
  purple: `absolute bottom-[20%] right-[10%] w-[350px] h-[350px] bg-[${colors.brand.primary}]/10 blur-[100px] rounded-full pointer-events-none`,
};

export { colors };
