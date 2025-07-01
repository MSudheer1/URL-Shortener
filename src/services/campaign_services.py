from os import name
import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update
from fastapi import HTTPException

from apps.shortener.models import CampaignSource, CampaignMedium, CampaignName
from apps.shortener.schemas import CampaignMediumUpdate, CampaignNameUpdate, CampaignSourceUpdate


# ======================
# Campaign Source Services
# ======================

def generate_unique_id(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def create_campaign_source(db: AsyncSession, user_id, campaign_source_tag, campaign_source_name):
    unique_id = generate_unique_id()
    new_source = CampaignSource(
        unique_id=unique_id,
        user_id=user_id,
        campaign_source_tag=campaign_source_tag,
        campaign_source_name=campaign_source_name
    )
    db.add(new_source)
    await db.commit()
    await db.refresh(new_source)
    return {"user_id": user_id, "unique_id": unique_id,"campaign_source_tag":campaign_source_tag,"campaign_source_name":campaign_source_name}

async def get_campaign_sources_by_user(db: AsyncSession, user_id):
    result = await db.execute(select(CampaignSource).where(CampaignSource.user_id == user_id))
    return result.scalars().all()

async def update_campaign_source(
    db: AsyncSession,
    user_id: str,
    unique_id: str,
    payload: CampaignSourceUpdate
):
    result = await db.execute(
        select(CampaignSource).where(
            CampaignSource.user_id == user_id,
            CampaignSource.unique_id == unique_id
        )
    )
    source = result.scalar_one_or_none()

    if not source:
        return {"status": "failed", "message": "No matching record found"}

    # Update only the provided fields
    if payload.campaign_source_tag is not None:
        source.campaign_source_tag = payload.campaign_source_tag

    if payload.campaign_source_name is not None:
        source.campaign_source_name = payload.campaign_source_name

    await db.commit()

    return {
        "status": "success",
        "unique_id": source.unique_id,
        "message": "Campaign source updated successfully"
    }



async def delete_campaign_source(db: AsyncSession, user_id, unique_id):
    result = await db.execute(
        select(CampaignSource).where(
            CampaignSource.user_id == user_id,
            CampaignSource.unique_id == unique_id
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        return {"status": "failed", "message": "No matching record found"}

    await db.delete(source)
    await db.commit()
    return {"status": "success", "message": "Deleted successfully"}

# ======================
# Campaign Medium Services
# ======================


async def create_campaign_medium(db: AsyncSession, user_id: str, medium_tag: str, medium_name: str):
    unique_id = generate_unique_id(6)  # assuming you have a random code generator

    new_medium = CampaignMedium(
        unique_id=unique_id,
        user_id=user_id,
        campaign_medium_tag=medium_tag,
        campaign_medium_name=medium_name
    )

    db.add(new_medium)
    await db.commit()
    await db.refresh(new_medium)
    return {"user_id": user_id, "unique_id": unique_id,"campaign_medium_tag":medium_tag,"campaign_medium_name":medium_name}

async def get_campaign_mediums_by_user(db: AsyncSession, user_id):
    result = await db.execute(select(CampaignMedium).where(CampaignMedium.user_id == user_id))
    return result.scalars().all()

async def update_campaign_medium(
    db: AsyncSession,
    user_id: str,
    unique_id: str,
    payload: CampaignMediumUpdate
):
    result = await db.execute(
        select(CampaignMedium).where(
            CampaignMedium.user_id == user_id,
            CampaignMedium.unique_id == unique_id
        )
    )
    medium = result.scalar_one_or_none()

    if not medium:
        return {"status": "failed", "message": "No matching record found"}

    # Update only if values are provided
    if payload.campaign_medium_tag is not None:
        medium.campaign_medium_tag = payload.campaign_medium_tag

    if payload.campaign_medium_name is not None:
        medium.campaign_medium_name = payload.campaign_medium_name

    await db.commit()

    return {
        "status": "success",
        "unique_id": medium.unique_id,
        "message": "Campaign medium updated successfully"
    }



async def delete_campaign_medium(db: AsyncSession, user_id, unique_id):
    result = await db.execute(
        select(CampaignMedium).where(
            CampaignMedium.user_id == user_id,
            CampaignMedium.unique_id == unique_id
        )
    )
    medium = result.scalar_one_or_none()
    if not medium:
        return {"status": "failed", "message": "No matching record found"}

    await db.delete(medium)
    await db.commit()
    return {"status": "success", "message": "Deleted successfully"}

# ======================
# Campaign Name Services
# ======================

async def create_campaign_name(db: AsyncSession, user_id: str, name_tag: str, name: str):
    unique_id = generate_unique_id(6)

    new_name = CampaignName(
        unique_id=unique_id,
        user_id=user_id,
        campaign_name_tag= name_tag,
        campaign_name= name
    )

    db.add(new_name)
    await db.commit()
    await db.refresh(new_name)
    return {"user_id": user_id, "unique_id": unique_id,"campaign_name_tag":name_tag,"campaign_name":name}

async def get_campaign_names_by_user(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(CampaignName).where(CampaignName.user_id == user_id)
    )
    return result.scalars().all()


async def update_campaign_name(
    db: AsyncSession,
    user_id: str,
    unique_id: str,
    payload: CampaignNameUpdate
):
    result = await db.execute(
        select(CampaignName).where(
            CampaignName.user_id == user_id,
            CampaignName.unique_id == unique_id
        )
    )
    name_record = result.scalar_one_or_none()

    if not name_record:
        return {"status": "failed", "message": "No matching record found"}

    # Only update if a value is provided
    if payload.campaign_name_tag is not None:
        name_record.campaign_name_tag = payload.campaign_name_tag

    if payload.campaign_name is not None:
        name_record.campaign_name = payload.campaign_name

    await db.commit()

    return {
        "status": "success",
        "unique_id": name_record.unique_id,
        "message": "Campaign name updated successfully"
    }


async def delete_campaign_name(db: AsyncSession, user_id: str, unique_id: str):
    result = await db.execute(
        select(CampaignName).where(
            CampaignName.user_id == user_id,
            CampaignName.unique_id == unique_id
        )
    )
    name = result.scalar_one_or_none()

    if not name:
        return {"status": "failed", "message": "No matching record found"}

    await db.delete(name)
    await db.commit()

    return {"status": "success", "message": "Deleted successfully"} 