from typing import Optional, List

from pydantic.v1 import BaseModel


class ProjectMonitoringListModel(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class GroupMonitoringListModel(BaseModel):
    id: int
    name: str
    # projects: Optional[List[ProjectMonitoringListModel]]

    class Config:
        orm_mode = True
