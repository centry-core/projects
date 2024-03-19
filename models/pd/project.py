from typing import Optional

from pydantic import BaseModel, EmailStr, constr


class ProjectCreatePD(BaseModel):
    name: constr(min_length=1)
    project_admin_email: EmailStr
    plugins: list = []
    data_retention_limit: int = 1_000_000_000
    # storage_space_limit: int = 1_000_000_000
    # vuh_limit: int = 60000
    test_duration_limit: int = -1
    cpu_limit: int = -1
    memory_limit: int = -1
    vcu_hard_limit: int = 5000
    vcu_soft_limit: int = 4700
    vcu_limit_total_block: bool = False
    storage_hard_limit: int = 10
    storage_soft_limit: int = 9
    storage_limit_total_block: bool = False
    invitation_integration: Optional[str] = None  # task_id
