import asyncio
import os
from server.api.services.supabase_client import SupabaseManager

async def test_supabase_connection():
    # Mock environment variables for the test
    # In a real scenario, these would be in .env
    os.environ["SUPABASE_URL"] = "https://your-project-url.supabase.co"
    os.environ["SUPABASE_KEY"] = "your-anon-key"

    print("--- Testing SupabaseManager Initialization ---")
    try:
        manager = SupabaseManager()
        print("Successfully initialized SupabaseManager")
    except Exception as e:
        print(f"Initialization failed (expected if keys are fake): {e}")
        return

    # Since we are using fake keys, the actual network calls will fail.
    # To truly verify the logic, we would need real keys or a mock client.
    # For this verification script, we check if methods are defined and handle errors gracefully.

    test_agent_id = "00000000-0000-0000-0000-000000000000"

    print("\n--- Testing get_agent_strategy ---")
    res = await manager.get_agent_strategy(test_agent_id)
    print(f"Result: {res} (Expected None/Error with fake keys)")

    print("\n--- Testing save_strategy ---")
    res = await manager.save_strategy(
        agent_id=test_agent_id,
        code="print('hello')",
        rationale="test rationale",
        params={"p": 1}
    )
    print(f"Result: {res} (Expected None/Error with fake keys)")

    print("\n--- Testing save_backtest ---")
    res = await manager.save_backtest("00000000-0000-0000-0000-000000000000", {"trinity_score": 85.5})
    print(f"Result: {res} (Expected False with fake keys)")

    print("\n--- Testing save_improvement_log ---")
    res = await manager.save_improvement_log(
        agent_id=test_agent_id,
        prev_id=None,
        new_id=None,
        analysis="test analysis",
        expected={"gain": "10%"}
    )
    print(f"Result: {res} (Expected False with fake keys)")

if __name__ == "__main__":
    asyncio.run(test_supabase_connection())
