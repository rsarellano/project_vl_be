from app.models.stored_svg.svg_element import SVGElement
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.svg_schemas.svg_elements_schema import SVGElementBase
from app.services.svg_services import svg_elements_service





async def create_svg_element(db: AsyncSession, data: SVGElementBase ):
    
    svg_element_data = data.model_dump()
    
    new_svg_element = SVGElement(**svg_element_data)
    db.add(new_svg_element)
    await db.commit()
    await db.refresh(new_svg_element)
    return new_svg_element


 