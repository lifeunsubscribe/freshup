from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SourceStatusResponse(BaseModel):
    """Health status for one recipe source, as returned by GET /sources/health."""
    source_type: str
    # 'healthy' | 'failing' | 'never_checked'
    status: str
    checked_at: Optional[datetime] = None
    # checked_at of the first row in the current consecutive failing streak
    failing_since: Optional[datetime] = None
    detail: Optional[str] = None
    # 'link' | 'saved_page' — null when never checked
    import_mode: Optional[str] = None
