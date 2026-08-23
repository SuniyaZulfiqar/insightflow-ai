from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatasetResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    filename: str
    file_type: str
    file_path: str
    row_count: int
    column_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class DatasetCleanRequest(BaseModel):
    fill_missing: bool = True
    remove_duplicates: bool = True