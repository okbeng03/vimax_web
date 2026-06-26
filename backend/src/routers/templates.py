"""Templates API router — list, create, update, delete templates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.models.template import Template
from src.schemas.template import (
    TemplateListResponse,
    TemplateResponse,
    TemplateCreate,
    TemplateUpdate,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates(db: AsyncSession = Depends(get_db)):
    """Get all available templates."""
    result = await db.execute(select(Template).order_by(Template.id))
    templates = result.scalars().all()
    return TemplateListResponse(
        templates=[TemplateResponse.model_validate(t) for t in templates],
    )


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(body: TemplateCreate, db: AsyncSession = Depends(get_db)):
    """Create a custom template."""
    existing = await db.execute(select(Template).where(Template.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Template '{body.name}' already exists")

    template = Template(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        directory_name=body.directory_name,
        is_builtin=False,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: int, body: TemplateUpdate, db: AsyncSession = Depends(get_db)):
    """Update a template (custom templates only)."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_builtin:
        raise HTTPException(status_code=403, detail="Built-in templates cannot be modified")

    update_data = body.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(template, key, val)
    await db.commit()
    await db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a template (custom templates only)."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_builtin:
        raise HTTPException(status_code=403, detail="Built-in templates cannot be deleted")

    await db.delete(template)
    await db.commit()
    return None
