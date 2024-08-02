from typing import List

from pydantic import BaseModel


class GroupModifyModel(BaseModel):
    groups: List[str]
    project_id: int


class GroupListModel(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class GroupCreateModel(BaseModel):
    name: str
    project_id: int
