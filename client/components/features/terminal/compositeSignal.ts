import type { HunterRow } from "./hunterRuntime";
import type { CoinData } from "@/components/features/crime/crimeData";

export type CrimeStage = "NONE" | "ACCUMULATE" | "SPRING" | "PRE_IGNITION" | "IGNITION";

export interface EnrichedRow extends HunterRow {
  crimeScore:     number;
  crimeStage:     CrimeStage;
  squeezeFuel:    number;
  compositeScore: number;
}

export interface CompositeAlert {
  sym:            string;
  full:           string;
  crimeStage:     CrimeStage;
  hunterStage:    number;
  squeezeFuel:    number;
  compositeScore: number;
  ts:             number;
}

export function normalizeCrimeStage(raw: string): CrimeStage {
  const s = raw.toUpperCase();
  if (s.includes("IGNITION") && !s.includes("PRE")) return "IGNITION";
  if (s.includes("PRE_IGNITION") || s.includes("PRE IGNITION")) return "PRE_IGNITION";
  if (s.includes("SPRING")) return "SPRING";
  if (s.includes("ACCUMULATE") || s.includes("ACCUM")) return "ACCUMULATE";
  return "NONE";
}

export function computeCompositeScore(
  crimeScore: number,
  regimeMult: number,
  confirmedExchanges: number
): number {
  const crossBonus =
    confirmedExchanges >= 3 ? 1.5 :
    confirmedExchanges >= 2 ? 1.2 :
    1.0;
  return Math.round(crimeScore * regimeMult * crossBonus);
}

export function isCompositeSignal(row: EnrichedRow): boolean {
  return (
    row.stage >= 2 &&
    (row.crimeStage === "PRE_IGNITION" || row.crimeStage === "IGNITION") &&
    row.squeezeFuel > 75
  );
}

export function mergeRows(
  hunterRows: HunterRow[],
  crimeResults: CoinData[]
): EnrichedRow[] {
  const crimeMap = new Map(crimeResults.map(c => [c.symbol, c]));

  return hunterRows.map(row => {
    const crime           = crimeMap.get(row.full);
    const crimeScore      = crime?.score ?? 0;
    const crimeStage      = normalizeCrimeStage(crime?.pump_stage ?? "");
    const squeezeFuel     = crime?.squeeze_fuel ?? 0;
    const confirmedExchanges = 1 + (row.aGradeActive ? 1 : 0) + (row.setupCount >= 3 ? 1 : 0);
    const compositeScore  = computeCompositeScore(crimeScore, row.regimeMult, confirmedExchanges);

    return { ...row, crimeScore, crimeStage, squeezeFuel, compositeScore };
  });
}
