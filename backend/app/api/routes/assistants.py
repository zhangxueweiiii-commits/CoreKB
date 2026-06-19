from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse, AssistantPresetRead
from app.services.assistant_preset_service import list_assistant_presets
from app.services.assistant_service import AssistantService

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.get("/presets", response_model=list[AssistantPresetRead])
def presets(_: User = Depends(get_current_user)) -> list[dict]:
    return [preset.to_dict() for preset in list_assistant_presets()]


@router.post("/{assistant_type}/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    assistant_type: str,
    payload: AssistantChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssistantChatResponse:
    return await AssistantService().chat(db=db, user=current_user, assistant_type=assistant_type, payload=payload)
