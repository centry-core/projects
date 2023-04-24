from typing import Optional

from pydantic import BaseModel, EmailStr, constr


class ProjectCreatePD(BaseModel):
    name: constr(min_length=1)
    project_admin_email: EmailStr
    plugins: list = []
    data_retention_limit: int = 1000000000
    storage_space_limit: int = 1000000000
    vuh_limit: int = 60000
    invitation_integration: Optional[str] = None  # task_id
