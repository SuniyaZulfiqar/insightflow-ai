from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse, Response

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.dataset import DatasetResponse
from app.services.dataset_service import (
    build_dashboard_pdf,
    build_cleaned_dataset_csv,
    build_cleaned_dataset_pdf,
    build_dataset_report_pdf,
    clean_dataset,
    delete_dataset,
    get_dataset_analytics,
    get_dataset_charts,
    get_dataset_clean_preview,
    get_dataset_preview,
    get_dataset_quality,
    get_dataset_statistics,
    get_datasets_for_workspace,
    save_dataset_file,
)
from app.services.workspace_service import get_workspace_for_owner

router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
)


def _get_workspace(db: Session, current_user: User):
    workspace = get_workspace_for_owner(db, current_user.id)

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    return workspace


@router.get(
    "",
    response_model=list[DatasetResponse],
)
def list_my_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)
    return get_datasets_for_workspace(db, workspace.id)


@router.post(
    "/upload",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_dataset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    try:
        return save_dataset_file(
            db=db,
            workspace_id=workspace.id,
            file=file,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process dataset: {exc}",
        )


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_200_OK,
)
def delete_dataset_endpoint(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    try:
        delete_dataset(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete dataset: {exc}",
        )

    return {"deleted": True, "dataset_id": dataset_id}


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    try:
        return get_dataset_preview(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get("/{dataset_id}/statistics")
def dataset_statistics(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    try:
        return get_dataset_statistics(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get("/{dataset_id}/analytics")
def dataset_analytics(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    try:
        return get_dataset_analytics(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get("/{dataset_id}/quality")
def dataset_quality(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    try:
        return get_dataset_quality(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )



@router.post("/{dataset_id}/clean-preview")
def clean_preview_endpoint(
    dataset_id: int,
    body: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)
    fill_missing = bool(body.get("fill_missing", False))
    remove_duplicates = bool(body.get("remove_duplicates", False))

    try:
        return get_dataset_clean_preview(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
            fill_missing=fill_missing,
            remove_duplicates=remove_duplicates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{dataset_id}/download")
def download_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)
    try:
        from app.services.dataset_service import _get_dataset
        dataset = _get_dataset(db, dataset_id, workspace.id)
        path = dataset.file_path
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if dataset.file_type == "xlsx"
            else "text/csv"
        )
        return FileResponse(
            path=path,
            media_type=media_type,
            filename=f"{dataset.name}_cleaned.{dataset.file_type}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{dataset_id}/cleaned.csv")
def download_cleaned_csv(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)
    try:
        filename, csv_bytes = build_cleaned_dataset_csv(db, dataset_id, workspace.id)
        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to generate cleaned CSV: {exc}")


@router.get("/{dataset_id}/cleaned.pdf")
def download_cleaned_pdf(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)
    try:
        pdf = build_cleaned_dataset_pdf(db, dataset_id, workspace.id)
        return FileResponse(
            path=pdf,
            media_type="application/pdf",
            filename="cleaned_data.pdf",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to generate cleaned data PDF: {exc}")


@router.get("/{dataset_id}/report.pdf")
def download_report_pdf(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)
    try:
        pdf = build_dataset_report_pdf(db, dataset_id, workspace.id)
        pdf_path = Path(pdf)
        if not pdf_path.is_file():
            raise RuntimeError("Report PDF was not created.")
        return FileResponse(
            path=str(pdf_path.resolve()),
            media_type="application/pdf",
            filename=f"InsightFlow_Report_{dataset_id}.pdf",
            headers={"Content-Disposition": f'attachment; filename="InsightFlow_Report_{dataset_id}.pdf"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to generate report PDF: {exc}")


@router.get("/{dataset_id}/dashboard.pdf")
def download_dashboard_pdf(
    dataset_id: int,
    columns: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)
    try:
        pdf = build_dashboard_pdf(db, dataset_id, workspace.id, columns=columns)
        return FileResponse(
            path=pdf,
            media_type="application/pdf",
            filename=f"InsightFlow_Dashboard_{dataset_id}.pdf",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unable to generate dashboard PDF: {exc}")


@router.post("/{dataset_id}/clean")
def clean_dataset_endpoint(
    dataset_id: int,
    body: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    fill_missing = bool(body.get("fill_missing", False))
    remove_duplicates = bool(body.get("remove_duplicates", False))

    if not fill_missing and not remove_duplicates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one cleaning action.",
        )

    try:
        return clean_dataset(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
            fill_missing=fill_missing,
            remove_duplicates=remove_duplicates,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clean dataset: {exc}",
        )


@router.get("/{dataset_id}/charts")
def dataset_charts(
    dataset_id: int,
    columns: Optional[str] = Query(
        default=None,
        description="Comma-separated column names selected by the user.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_workspace(db, current_user)

    try:
        return get_dataset_charts(
            db=db,
            dataset_id=dataset_id,
            workspace_id=workspace.id,
            columns=columns,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
