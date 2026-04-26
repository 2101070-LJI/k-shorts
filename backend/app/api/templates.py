from fastapi import APIRouter, HTTPException

from app.services.template_loader import load_all, load_one

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
def list_templates() -> list[dict]:
    return load_all()


@router.get("/{template_id}")
def get_template(template_id: str) -> dict:
    tpl = load_one(template_id)
    if tpl is None:
        raise HTTPException(404, f"template not found: {template_id}")
    return tpl
