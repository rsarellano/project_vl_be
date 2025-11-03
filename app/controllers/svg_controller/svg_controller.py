
from app.schemas.svg_schemas.svg_elements_schema import SVGElementCreate, SVGElementRead, SVGElementBase
from app.services.svg_services.svg_elements_service import create_svg_element
from app.db.database.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, status, Depends



router = APIRouter(prefix="/svg-elements",
                   tags=["svg_elements"]
                   )


@router.post("/", response_model=SVGElementRead, status_code=status.HTTP_201_CREATED)
async def create_new_svg(svg_element: SVGElementBase, db: AsyncSession = Depends(get_db)):

        return await create_svg_element(db,svg_element)
