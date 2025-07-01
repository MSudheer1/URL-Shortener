import httpx

async def get_location_from_ip(ip: str) -> dict:
    url = f"https://ipapi.co/{ip}/json/"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                "city": data.get("city", "Unknown"),
                "country": data.get("country_name", "Unknown"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
            }
    return {
        "city": "Unknown",
        "country": "Unknown",
        "latitude": None,
        "longitude": None,
    }
