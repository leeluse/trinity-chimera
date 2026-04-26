import { Suspense } from "react";
import BacktestClientPage from "./BacktestClientPage";

export default function BacktestPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <BacktestClientPage />
    </Suspense>
  );
}
