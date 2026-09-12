"""Open-Meteo adapter. Not yet wired into placeholder replanning."""
import httpx


async def fetch_weather(latitude: float, longitude: float) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": latitude, "longitude": longitude,
            "hourly": "precipitation_probability", "timezone": "Asia/Tokyo",
            "forecast_days": 1,
        })
        response.raise_for_status()
        return response.json()
