import asyncio
from app.services.text_to_sql_service import detect_database_query_intent, run_text_to_sql

async def test():
    # Test 1: Intent detection
    msg = "Please refer to the users table and tell me the total number of users"
    intent = await detect_database_query_intent(msg, "test@amzur.com")
    print(f"Intent detected: {intent}")
    
    # Test 2: SQL generation and execution
    if intent:
        try:
            result = await run_text_to_sql(msg, "test@amzur.com")
            print(f"SQL Result:\n{result}")
        except Exception as e:
            print(f"Error during execution: {e}")

asyncio.run(test())
