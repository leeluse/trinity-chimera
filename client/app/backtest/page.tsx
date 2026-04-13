import { Suspense } from "react";
import BacktestClientPage from "./BacktestClientPage";

export default function BacktestPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#05070f]" />}>
      <BacktestClientPage />
    </Suspense>
  );
}
