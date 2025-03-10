import asyncio
import json
import sys

async def test_server():
    # Send a test request
    request = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    }
    
    print("Sending test request:", json.dumps(request))
    print(json.dumps(request), file=sys.stdout, flush=True)
    
    # Wait for response
    response = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
    print("Received response:", response.strip())

if __name__ == "__main__":
    asyncio.run(test_server())
