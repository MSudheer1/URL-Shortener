from sqlalchemy import select
import httpx
import socket
import user_agents
from sqlmodel.ext.asyncio.session import AsyncSession
from apps.shortener.models import VisitLog
from datetime import datetime
from fastapi import Request

from utils.system_utils import get_system_id


def get_system_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address


async def get_public_ip():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api64.ipify.org?format=json")
            if response.status_code == 200:
                return response.json().get("ip", "127.0.0.1")
    except Exception as e:
        print(f"Failed to get public IP: {e}")
    return "127.0.0.1"


class VisitService:

    async def log_visit(
        self,
        db: AsyncSession,
        request: Request,
        short_code: str,
        # domain: Optional[str] = None
    ):
        
        system_id = get_system_id()

        client_ip = request.headers.get("X-Forwarded-For", request.client.host)
        if client_ip == "127.0.0.1":
            client_ip = await get_public_ip()

        system_id = get_system_id()

        user_agent_string = request.headers.get("user-agent", "Unknown")
        ua = user_agents.parse(user_agent_string)

        device = (
            "Mobile" if ua.is_mobile
            else "Tablet" if ua.is_tablet
            else "PC" if ua.is_pc
            else "Other"
        )
        os = ua.os.family if ua.os.family else "Other"
        browser = ua.browser.family if ua.browser.family else "Other"

        city, country = "Unknown", "Unknown"
        latitude, longitude = None, None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://ipapi.co/{client_ip}/json/")
                if response.status_code == 200:
                    data = response.json()
                    city = data.get("city", "Unknown")
                    country = data.get("country_name", "Unknown")
                    latitude = data.get("latitude")
                    longitude = data.get("longitude")
        except Exception as e:
            print(f"Geo lookup failed: {e}")

        print(f"IP: {client_ip}, City: {city}, Country: {country}, OS: {os}, Browser: {browser}, Device: {device}")


        visit = VisitLog(
            short_url=short_code,
            client_ip=client_ip,
            city=city,
            country=country,
            latitude=latitude,
            longitude=longitude,
            device=device,
            os=os,
            browser=browser,
            visited_at=datetime.utcnow(),
            system_id =system_id
        )

        db.add(visit)
        await db.commit()
        
    async def get_visits_by_client_ip(self, db: AsyncSession, client_ip: str):
        result = await db.execute(
            select(VisitLog).where(VisitLog.client_ip == client_ip)
        )
        return result.scalars().all()

visit_service = VisitService()
