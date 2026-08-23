from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import Workspace


def get_workspace_for_owner(
    db: Session,
    owner_id: int,
) -> Workspace | None:
    statement = (
        select(Workspace)
        .where(Workspace.owner_id == owner_id)
        .order_by(Workspace.id)
    )

    return db.scalars(statement).first()