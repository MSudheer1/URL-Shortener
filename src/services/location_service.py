import httpx
async def get_location_from_ip(ip: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://ip-api.com/json/{ip}")
            data = response.json()

            if data["status"] == "success":
                return {
                    "city": data.get("city", "Unknown"),
                    "country": data.get("country", "Unknown"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon")
                }
    except Exception as e:
        print(f"Error fetching geolocation: {e}")

    return {
        "city": "Unknown",
        "country": "Unknown",
        "latitude": None,
        "longitude": None
    }
