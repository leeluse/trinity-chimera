



from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
from server.modules.scanner.crime_hunter import get_crime_hunter_scanner

router = APIRouter(prefix="/scanner", tags=["Scanner"])
scanner = get_crime_hunter_scanner()

@router.post("/run")
async def run_scan(background_tasks: BackgroundTasks):
    """
    Triggers a full market scan in the background.
    """
    if scanner.is_scanning:
        return {"status": "already_scanning", "message": "A scan is already in progress."}
    
    background_tasks.add_task(scanner.scan)
    return {"status": "started", "message": "Market scan started in background."}

@router.get("/results")
async def get_results():
    """
    Returns the results of the latest scan.
    """
    return {
        "count": len(scanner.last_results),
        "is_scanning": scanner.is_scanning,
        "results": [
            {
                "symbol": c.symbol,
                "score": c.score,
                "pump_stage": c.pump_stage,
                "price": c.price,
                "funding_rate": c.funding_rate,
                "oi_change_1h": c.oi_change_pct_1h,
                "price_change_1h": c.price_change_1h,
                "risk": {
                    "trap_risk": c.risk.dump_trap_risk,
                    "leverage": c.risk.recommended_leverage,
                    "stop_loss": c.risk.stop_loss,
                    "rr": c.risk.risk_reward
                },
                "reasons": c.score_reasons
            }
            for c in scanner.last_results
        ]
    }

@router.get("/status")
async def get_status():
    return {
        "is_scanning": scanner.is_scanning,
        "last_scan_count": len(scanner.last_results)
    }
