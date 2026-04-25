"""
봇 생명주기 관리 및 스케줄링
"""
import logging
from typing import Dict, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .simulator import BotSimulator
from server.shared.db.supabase import SupabaseManager

logger = logging.getLogger(__name__)

class BotManager:
    """봇 인스턴스 관리 및 실행"""

    _instance: Optional['BotManager'] = None
    _active_bots: Dict[str, BotSimulator] = {}
    _scheduler: Optional[AsyncIOScheduler] = None
    _db: Optional[SupabaseManager] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._db = SupabaseManager()

    @classmethod
    def set_scheduler(cls, scheduler: AsyncIOScheduler):
        """스케줄러 등록 (main.py에서 호출)"""
        cls._scheduler = scheduler

    async def load_active_bots(self):
        """DB에서 활성 봇 로드 및 초기화"""
        try:
            bots = await self._db.list_bots(limit=100)

            for bot in bots:
                if bot.get("is_active"):
                    bot_id = bot.get("id")

                    # 전략 코드 로드
                    strategy = await self._db.get_bot(bot_id)
                    if not strategy or not strategy.get("strategies"):
                        logger.warning(f"Bot {bot_id}: No strategy found")
                        continue

                    strategy_data = strategy["strategies"]
                    strategy_code = strategy_data.get("code")
                    strategy_name = strategy_data.get("name", "Unknown")

                    # 시뮬레이터 생성
                    config = {
                        "symbol": bot.get("symbol"),
                        "timeframe": bot.get("timeframe"),
                        "leverage": bot.get("leverage"),
                        "initial_capital": bot.get("initial_capital"),
                        "max_position_pct": bot.get("max_position_pct"),
                        "stop_loss_pct": bot.get("stop_loss_pct"),
                        "take_profit_pct": bot.get("take_profit_pct"),
                        "risk_profile": bot.get("risk_profile"),
                        "reinvest": bot.get("config", {}).get("reinvest", False)
                    }

                    simulator = BotSimulator(
                        bot_id=bot_id,
                        strategy_code=strategy_code,
                        strategy_name=strategy_name,
                        config=config
                    )

                    self._active_bots[bot_id] = simulator
                    logger.info(f"Bot {bot_id} ({strategy_name}) loaded and ready")

        except Exception as e:
            logger.exception(f"Error loading active bots: {e}")

    async def start_bot(self, bot_id: str) -> bool:
        """봇 시작"""
        try:
            bot_data = await self._db.get_bot(bot_id)
            if not bot_data:
                logger.error(f"Bot {bot_id}: Not found")
                return False

            # is_active = True로 설정
            await self._db.update_bot(bot_id, {"is_active": True})

            # 활성 봇 목록에 추가
            if bot_id not in self._active_bots:
                strategy = bot_data.get("strategies", {})
                config = {
                    "symbol": bot_data.get("symbol"),
                    "timeframe": bot_data.get("timeframe"),
                    "leverage": bot_data.get("leverage"),
                    "initial_capital": bot_data.get("initial_capital"),
                    "max_position_pct": bot_data.get("max_position_pct"),
                    "stop_loss_pct": bot_data.get("stop_loss_pct"),
                    "take_profit_pct": bot_data.get("take_profit_pct"),
                    "risk_profile": bot_data.get("risk_profile"),
                }

                simulator = BotSimulator(
                    bot_id=bot_id,
                    strategy_code=strategy.get("code", ""),
                    strategy_name=strategy.get("name", "Unknown"),
                    config=config
                )
                self._active_bots[bot_id] = simulator

            logger.info(f"Bot {bot_id} started")
            return True

        except Exception as e:
            logger.exception(f"Error starting bot {bot_id}: {e}")
            return False

    async def stop_bot(self, bot_id: str) -> bool:
        """봇 중지"""
        try:
            # is_active = False로 설정
            await self._db.update_bot(bot_id, {"is_active": False})

            # 활성 봇 목록에서 제거
            if bot_id in self._active_bots:
                del self._active_bots[bot_id]

            logger.info(f"Bot {bot_id} stopped")
            return True

        except Exception as e:
            logger.exception(f"Error stopping bot {bot_id}: {e}")
            return False

    async def get_bot_state(self, bot_id: str) -> Optional[Dict]:
        """봇 현재 상태 조회"""
        if bot_id not in self._active_bots:
            return None
        return self._active_bots[bot_id]._get_state_snapshot()

    async def run_active_bots_tick(self):
        """활성 봇 1틱 실행 (스케줄러에서 주기적으로 호출)"""
        from datetime import datetime

        logger.debug(f"Running tick for {len(self._active_bots)} active bots")

        for bot_id, simulator in list(self._active_bots.items()):
            try:
                # 현재가 수집 (binance에서 가져옴)
                current_price = await self._fetch_current_price(simulator.symbol)
                if current_price is None:
                    logger.warning(f"Bot {bot_id}: Failed to fetch price for {simulator.symbol}")
                    continue

                # 시뮬레이터 상태 업데이트
                state = await simulator.update_state(current_price, datetime.now())

                # DB에 상태 저장
                await self._db.update_bot(bot_id, {"sim_state": state})

            except Exception as e:
                logger.error(f"Error running bot {bot_id} tick: {e}")

    async def _fetch_current_price(self, symbol: str) -> Optional[float]:
        """Binance에서 현재가 조회"""
        try:
            import aiohttp
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data.get("price", 0))
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        return None

    @property
    def active_bots_count(self) -> int:
        return len(self._active_bots)

    def get_all_active_bots(self) -> Dict[str, BotSimulator]:
        return self._active_bots.copy()
