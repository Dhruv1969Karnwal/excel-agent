import httpx
import json
import urllib.parse

DOKPLOY_BASE_URL = "http://35.232.206.182:3000"
SESSION_TOKEN = "y6Tp1ORUbv0BFbwMPbSXNZPbaCN9eNpt.r6H5aO6sv2pZ5IZ8LmOcQYkgqi%2FIzeASG94ruhBmF5A%3D"
PROJECT_ID = "lOOolgBk2tY-wpFRvySUk"
APP_ID = "BYTpBGzcJYka0VI6yblxE" # Example from user
APP_NAME = "app-compress-online-bus-ycosyy" # Example from user

async def debug_trpc():
    input_data = {
        "0": {"json": None, "meta": {"values": ["undefined"]}},
        "1": {"json": None, "meta": {"values": ["undefined"]}},
        "2": {"json": {"applicationId": APP_ID}},
        "3": {"json": {"appName": APP_NAME, "serverId": ""}},
        "4": {"json": {"projectId": PROJECT_ID}},
        "5": {"json": {"containerId": "select-a-container", "serverId": ""}}
    }
    
    encoded_input = urllib.parse.quote(json.dumps(input_data))
    url = f"{DOKPLOY_BASE_URL}/api/trpc/organization.all,user.getInvitations,application.one,docker.getContainersByAppNameMatch,environment.byProjectId,docker.getConfig?batch=1&input={encoded_input}"
    
    headers = {
        "Cookie": f"better-auth.session_token={SESSION_TOKEN}"
    }
    
    print(f"Requesting URL: {url}")
    print(f"Headers: {headers}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_trpc())
