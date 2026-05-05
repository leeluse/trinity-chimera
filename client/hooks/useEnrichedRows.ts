import { useMemo } from "react";
import { useTerminalStore } from "@/components/features/terminal/terminalStore";
import { useCrimeStore }    from "@/store/useCrimeStore";
import { mergeRows }        from "@/components/features/terminal/compositeSignal";
import type { EnrichedRow } from "@/components/features/terminal/compositeSignal";

export function useEnrichedRows(): EnrichedRow[] {
  const hunterRows   = useTerminalStore(s => s.hunterRows);
  const crimeResults = useCrimeStore(s => s.results);

  return useMemo(
    () => mergeRows(hunterRows, crimeResults),
    [hunterRows, crimeResults]
  );
}
