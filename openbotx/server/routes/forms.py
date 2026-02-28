from fastapi import APIRouter

from openbotx.config.form import FORM_SCHEMAS

router = APIRouter()


@router.get("")
async def get_forms():
    return FORM_SCHEMAS
