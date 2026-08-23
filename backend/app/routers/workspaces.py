from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.workspace import WorkspaceResponse
from app.services.workspace_service import get_workspace_for_owner


router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)


@router.get(
    "/me",
    response_model=WorkspaceResponse,
)
def get_my_workspace(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = get_workspace_for_owner(
        db,
        current_user.id,
    )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    return workspace