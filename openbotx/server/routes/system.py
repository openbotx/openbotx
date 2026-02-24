from fastapi import APIRouter

from openbotx.version import __version__

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/version")
async def version():
    return {"version": __version__}
