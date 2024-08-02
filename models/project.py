#     Copyright 2020 getcarrier.io
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
from typing import Optional, List

from ..models.pd.project import ProjectListModel
from sqlalchemy import String, Column, Integer, JSON, ARRAY, Text, Boolean, ForeignKey, Table
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import select

from tools import rpc_tools, db, db_tools, MinioClient, config as c

from sqlalchemy.orm import Mapped, relationship, joinedload


class ProjectGroup(db.Base):
    __tablename__ = "project_group"
    __table_args__ = {"schema": c.POSTGRES_SCHEMA}

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False, unique=True)

    projects: Mapped[List['Project']] = relationship(
        secondary=lambda: ProjectGroupAssociation,
        backref='group',
        # back_populates='group',
        lazy='dynamic'
    )


ProjectGroupAssociation = Table(
    'project_group_association',
    db.Base.metadata,
    Column('project_id', ForeignKey(f'{c.POSTGRES_SCHEMA}.project.id')),
    Column('group_id', ForeignKey(f'{c.POSTGRES_SCHEMA}.{ProjectGroup.__tablename__}.id')),
    schema=c.POSTGRES_SCHEMA
)


class Project(db_tools.AbstractBaseMixin, rpc_tools.RpcMixin, db.Base):
    __tablename__ = "project"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    owner_id = Column(Integer, nullable=False)
    secrets_json = Column(JSON, default={})
    # worker_pool_config_json = Column(JSON, unique=False, default={})
    plugins = Column(ARRAY(Text), default={})
    keycloak_groups = Column(
        'keycloak_groups', MutableDict.as_mutable(JSON),
        nullable=False, default={},
    )
    create_success = Column(Boolean, nullable=False, default=False)
    groups: Mapped[List[ProjectGroup]] = relationship(
        secondary=lambda: ProjectGroupAssociation,
        backref='project',
        # back_populates='project',
        lazy='joined'
    )

    def get_data_retention_limit(self) -> Optional[int]:
        from .quota import ProjectQuota
        project_quota = ProjectQuota.query.filter_by(project_id=self.id).first()
        if project_quota and project_quota.data_retention_limit:
            return project_quota.data_retention_limit

    @staticmethod
    def get_storage_space_quota(project_id):
        from .quota import ProjectQuota
        project_quota = ProjectQuota.query.filter_by(project_id=project_id).first()
        if project_quota:
            return project_quota.storage_soft_limit_in_bytes, project_quota.storage_hard_limit_in_bytes

    @staticmethod
    def list_projects(project_id: int = None, search_: str = None,
                      limit_: int = None, offset_: int = None,
                      filter_: Optional[dict] = None, **kwargs) -> dict | list[dict] | None:
        flt = []
        if filter_ is not None:
            for k, v in filter_.items():
                attr = getattr(Project, k)
                if attr:
                    flt.append(attr == v)
        with db.with_project_schema_session(None) as session:
            if project_id:
                stmt = select(Project).where(Project.id == project_id)
                p = session.scalars(stmt).unique().first()
                if not p:
                    return

                return ProjectListModel.from_orm(p).dict()
            elif search_:
                stmt = select(Project).where(Project.name.ilike(f"%{search_}%")).limit(limit_).offset(offset_)
            else:
                stmt = select(Project).where(*flt).limit(limit_).offset(offset_)

            projects = session.scalars(stmt.options(joinedload(Project.groups))).unique().all()
            return [ProjectListModel.from_orm(project).dict() for project in projects]
