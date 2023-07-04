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
from queue import Empty
from typing import Optional, List, Union
from sqlalchemy import String, Column, Integer, JSON, ARRAY, Text, and_
from sqlalchemy.ext.mutable import MutableDict


from tools import rpc_tools, db, db_tools, MinioClient

from ..tools.session_project import SessionProject


class Project(db_tools.AbstractBaseMixin, rpc_tools.RpcMixin, db.Base):
    __tablename__ = "project"

    API_EXCLUDE_FIELDS = ("secrets_json", )

    id = Column(Integer, primary_key=True)
    name = Column(String(256), unique=False)
    owner_id = Column(Integer, unique=False)
    secrets_json = Column(JSON, unique=False, default={})
    # worker_pool_config_json = Column(JSON, unique=False, default={})
    plugins = Column(ARRAY(Text), unique=False, default={})
    keycloak_groups = Column(
        'keycloak_groups', MutableDict.as_mutable(JSON),
        nullable=False, default={},
    )
    # created_at =

    def insert(self) -> None:
        super().insert()

        # create keycloak group
        try:
            group_handler = self.rpc.timeout(5).project_keycloak_group_handler(self)
            group_handler.create_main_group()
            group_handler.create_subgroups()
        except Empty:
            ...

        mc = MinioClient(project=self)
        mc.create_bucket(bucket="reports", bucket_type='system')
        mc.create_bucket(bucket="tasks", bucket_type='system')
        # SessionProject.set(self.id) # todo: we need to set session project only to project admin, not for creator
        # SessionProjectPlugin.set(self.plugins)

    def used_in_session(self):
        selected_id = SessionProject.get()
        return self.id == selected_id

    def to_json(self, exclude_fields: tuple = tuple()) -> dict:
        json_data = super().to_json(exclude_fields=exclude_fields)
        return json_data

    def get_data_retention_limit(self) -> Optional[int]:
        from .quota import ProjectQuota
        project_quota = ProjectQuota.query.filter_by(project_id=self.id).first()
        if project_quota and project_quota.data_retention_limit:
            return project_quota.data_retention_limit

    @staticmethod
    def get_storage_space_quota(project_id):
        from .quota import ProjectQuota
        project_quota = ProjectQuota.query.filter_by(project_id=project_id).first()
        if project_quota and project_quota.storage_space:
            return project_quota.storage_space

    @staticmethod
    def get_or_404(project_id, exclude_fields=()):
        project = Project.query.get_or_404(project_id)
        # if not is_user_part_of_the_project(project.id):
        #     abort(404, description="User not a part of project")
        return project

    @staticmethod
    def list_projects(project_id: int = None, search_: str = None,
                      limit_: int = None, offset_: int = None, **kwargs) -> Union[dict, List[dict]]:
        # allowed_project_ids = only_users_projects()
        excluded_fields = Project.API_EXCLUDE_FIELDS + ('extended_out',)
        _filter = None
        # if "all" not in allowed_project_ids:
        #     _filter = Project.id.in_(allowed_project_ids)
        if project_id:
            project = Project.get_or_404(project_id)
            return project.to_json(exclude_fields=Project.API_EXCLUDE_FIELDS), 200
        elif search_:
            filter_ = Project.name.ilike(f"%{search_}%")
            if _filter is not None:
                filter_ = and_(_filter, filter_)
            projects = Project.query.filter(filter_).limit(limit_).offset(offset_).all()
        else:
            if _filter is not None:
                projects = Project.query.filter(_filter).limit(limit_).offset(offset_).all()
            else:
                projects = Project.query.limit(limit_).offset(offset_).all()
        return [project.to_json(exclude_fields=excluded_fields) for project in projects]
