from typing import List

from pydantic.v1 import BaseModel, validator


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

    @validator('name')
    def check_no_group_name(cls, name: str):
        assert name != 'no_group', 'Group with name "no_group" can not be created'
        return name

