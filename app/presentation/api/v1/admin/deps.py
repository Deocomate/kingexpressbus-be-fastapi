"""Admin route dependencies."""

from typing import Annotated

from fastapi import Depends

from app.core.deps import require_admin, require_same_origin
from app.infrastructure.persistence.models import User

AdminUser = Annotated[User, Depends(require_admin)]
SameOrigin = Annotated[None, Depends(require_same_origin)]
