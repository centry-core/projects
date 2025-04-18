from typing import Optional, List

from pydantic.v1 import BaseModel, constr
from .group import GroupListModel


class ProjectCreatePD(BaseModel):
    name: constr(min_length=1)
    project_admin_email: str
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


class ProjectListModel(BaseModel):
    id: int
    name: str
    owner_id: int
    plugins: Optional[List[str]]
    keycloak_groups: Optional[dict]
    create_success: Optional[bool]
    groups: List[GroupListModel]

    class Config:
        orm_mode = True

