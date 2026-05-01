"""API 路由模块"""
from app.routers.papers import router as papers_router
from app.routers.highlights import router as highlights_router
from app.routers.ws import router as ws_router
from app.routers.notes import router as notes_router
from app.routers.reading import router as reading_router
from app.routers.analysis import router as analysis_router
from app.routers.chat import router as chat_router
from app.routers.recommendations import router as recommendations_router
from app.routers.writing import router as writing_router
from app.routers.knowledge import router as knowledge_router
from app.routers.settings import router as settings_router
from app.routers.backup import router as backup_router
from app.routers.feature_flags import router as feature_flags_router
from app.routers.batch_analysis import router as batch_analysis_router
from app.routers.cost import router as cost_router
from app.routers.health import router as health_router
from app.routers.citations import router as citations_router
from app.routers.config import router as config_router
from app.routers.upload import router as upload_router
from app.routers.precache import router as precache_router
from app.routers.model_config import router as model_config_router
from app.routers.routing import router as routing_router
from app.routers.export import router as export_router
from app.routers.folder_import import router as folder_import_router
from app.routers.subagent import router as subagent_router

__all__ = [
    "papers_router",
    "highlights_router",
    "notes_router",
    "ws_router",
    "reading_router",
    "analysis_router",
    "chat_router",
    "recommendations_router",
    "writing_router",
    "knowledge_router",
    "settings_router",
    "backup_router",
    "feature_flags_router",
    "batch_analysis_router",
    "cost_router",
    "health_router",
    "citations_router",
    "config_router",
    "upload_router",
    "precache_router",
    "model_config_router",
    "routing_router",
    "export_router",
    "folder_import_router",
    "subagent_router",
]
