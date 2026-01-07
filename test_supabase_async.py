import asyncio
import os
from supabase import create_async_client
from dotenv import load_dotenv

load_dotenv()

async def test():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("Missing Supabase config")
        return
        
    client = await create_async_client(url, key)
    print(f"Client: {type(client)}")
    
    table_obj = client.table("videos")
    print(f"Table object type: {type(table_obj)}")
    
    if asyncio.iscoroutine(table_obj):
        print("Table is a coroutine!")
    else:
        print("Table is NOT a coroutine.")

if __name__ == "__main__":
    asyncio.run(test())
