from pydantic import BaseModel


class ProjectGroupModel(BaseModel):
    name: str
    project_id: int


class ProjectGroupListModel(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
