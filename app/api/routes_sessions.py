from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.session_identity import IdentityError, resolve_project_scope
from app.db.database import get_db
from app.db.models import Message

router = APIRouter()


@router.get("/sessions")
def sessions(user_id: str, project_id: str, db: Session = Depends(get_db)):
    try:
        scope = resolve_project_scope(user_id, project_id)
    except IdentityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows = db.query(Message.session_id).filter_by(user_id=scope.user_id, project_id=scope.project_id).distinct().all()
    return {"sessions": [r[0] for r in rows]}
