from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from pathlib import Path
from dotenv import load_dotenv, set_key

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"

class ModelSettings(BaseModel):
    # Chat settings
    chat_provider: str
    chat_model: str
    chat_base_url: str
    
    # Evolution settings
    evo_base_url: str
    evo_model: str
    evo_api_key: str

@router.get("/settings")
async def get_settings():
    """현재 .env에 설정된 주요 모델 정보 반환"""
    # 최신 상태를 읽기 위해 다시 로드 (단, 메모리 반영은 별개)
    load_dotenv(ENV_PATH, override=True)
    
    return {
        "chat_provider": os.getenv("LLM_PROVIDER", "ollama"),
        "chat_model": os.getenv("OLLAMA_MODEL", ""),
        "chat_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        
        "evo_base_url": os.getenv("ANTHROPIC_BASE_URL", "http://localhost:8082"),
        "evo_model": os.getenv("ANTHROPIC_MODEL", "qwen/qwen3.5-397b-a17b"),
        "evo_api_key": os.getenv("ANTHROPIC_API_KEY", "sk-dummy")
    }

@router.post("/settings")
async def update_settings(settings: ModelSettings):
    """.env 파일을 업데이트하여 설정을 반영함"""
    try:
        if not ENV_PATH.exists():
            # 파일이 없으면 생성
            ENV_PATH.touch()
            
        # .env 파일에 쓰기
        set_key(str(ENV_PATH), "LLM_PROVIDER", settings.chat_provider)
        set_key(str(ENV_PATH), "OLLAMA_MODEL", settings.chat_model)
        set_key(str(ENV_PATH), "OLLAMA_BASE_URL", settings.chat_base_url)
        
        set_key(str(ENV_PATH), "ANTHROPIC_BASE_URL", settings.evo_base_url)
        set_key(str(ENV_PATH), "ANTHROPIC_MODEL", settings.evo_model)
        set_key(str(ENV_PATH), "ANTHROPIC_API_KEY", settings.evo_api_key)
        # 하위 호환성을 위해 추가 키들도 업데이트
        set_key(str(ENV_PATH), "ANTHROPIC_DEFAULT_SONNET_MODEL", settings.evo_model)
        
        # 실제 환경 변수 메모리에도 반영 (현재 프로세스)
        os.environ["LLM_PROVIDER"] = settings.chat_provider
        os.environ["OLLAMA_MODEL"] = settings.chat_model
        os.environ["OLLAMA_BASE_URL"] = settings.chat_base_url
        os.environ["ANTHROPIC_BASE_URL"] = settings.evo_base_url
        os.environ["ANTHROPIC_MODEL"] = settings.evo_model
        os.environ["ANTHROPIC_API_KEY"] = settings.evo_api_key
        
        return {"success": True, "message": "설정이 저장되었습니다. 일부 핵심 엔진 반영을 위해 서버 재시작이 필요할 수 있습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
