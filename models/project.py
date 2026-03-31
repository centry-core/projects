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
from sqlalchemy import String, Column, Integer, JSON, ARRAY, Text, Boolean, ForeignKey, Table, asc, desc, func, case, cast, or_
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
        back_populates='groups',
        lazy='dynamic',
        overlaps="groups,project_group_association"
    )


ProjectGroupAssociation = Table(
    'project_group_association',
    db.Base.metadata,
    Column('project_id', ForeignKey(f'{c.POSTGRES_SCHEMA}.project.id', ondelete='CASCADE')),
    Column('group_id', ForeignKey(f'{c.POSTGRES_SCHEMA}.{ProjectGroup.__tablename__}.id', ondelete='CASCADE')),
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
    suspended = Column(Boolean, nullable=False, default=False, server_default='false')
    groups: Mapped[List[ProjectGroup]] = relationship(
        secondary=lambda: ProjectGroupAssociation,
        back_populates='projects',
        lazy='joined',
        overlaps="projects,project_group_association"
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
                      filter_: Optional[dict] = None,
                      **kwargs) -> dict | list[dict] | None:
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

            stmt = stmt.order_by(asc(Project.id))

            projects = session.scalars(stmt.options(joinedload(Project.groups))).unique().all()
            return [ProjectListModel.from_orm(project).dict() for project in projects]

    @staticmethod
    def list_projects_paginated(
        limit: int = 20,
        offset: int = 0,
        search: str = None,
        sort_by: str = "name",
        sort_order: str = "asc",
        project_type: str = None,
        owner_ids: list = None,
    ) -> dict:
        """List projects with DB-level pagination, filtering, sorting, and tab counts."""
        with db.with_project_schema_session(None) as session:
            # Tab counts (unfiltered by search/project_type)
            is_personal = Project.name.like("project_user_%")
            counts_stmt = select(
                func.count().label("total"),
                func.sum(case((is_personal, 1), else_=0)).label("personal"),
            ).select_from(Project)
            counts_row = session.execute(counts_stmt).one()
            personal_count = int(counts_row.personal or 0)
            team_count = int(counts_row.total) - personal_count
            #
            # Build filtered query
            #
            conditions = []
            if project_type == "personal":
                conditions.append(is_personal)
            elif project_type == "team":
                conditions.append(~is_personal)
            if search:
                search_conditions = [
                    Project.name.ilike(f"%{search}%"),
                    cast(Project.id, String).ilike(f"%{search}%"),
                ]
                if owner_ids:
                    search_conditions.append(Project.owner_id.in_(owner_ids))
                conditions.append(or_(*search_conditions))
            elif owner_ids:
                conditions.append(Project.owner_id.in_(owner_ids))
            #
            stmt = select(Project).where(*conditions) if conditions else select(Project)
            #
            # Count after filtering (for pagination total)
            #
            count_stmt = select(func.count()).select_from(Project)
            if conditions:
                count_stmt = count_stmt.where(*conditions)
            total = session.execute(count_stmt).scalar()
            #
            # Sorting
            #
            sort_map = {
                "name": Project.name,
                "id": Project.id,
                "create_success": Project.create_success,
                "status": case(
                    (Project.suspended == True, 3),
                    (Project.create_success == True, 0),
                    (Project.create_success == False, 2),
                    else_=1,
                ),
            }
            sort_col = sort_map.get(sort_by, Project.name)
            order_fn = desc if sort_order.lower() == "desc" else asc
            stmt = stmt.order_by(order_fn(sort_col))
            #
            # Pagination
            #
            stmt = stmt.limit(limit).offset(offset)
            stmt = stmt.options(joinedload(Project.groups))
            projects = session.scalars(stmt).unique().all()
            rows = [ProjectListModel.from_orm(p).dict() for p in projects]
            #
            return {
                "rows": rows,
                "total": total,
                "counts": {
                    "personal": personal_count,
                    "team": team_count,
                },
            }
