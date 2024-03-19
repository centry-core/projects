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

from sqlalchemy import Column, Integer, DateTime, Boolean
from datetime import datetime, timedelta

from tools import db, db_tools, data_tools

from typing_extensions import Optional
from .statistics import Statistic


class ProjectQuota(db_tools.AbstractBaseMixin, db.Base):
    __tablename__ = "project_quota"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, unique=False, nullable=False)
    # vuh_limit = Column(Integer, unique=False, nullable=False)
    # storage_space = Column(Integer, unique=False)
    data_retention_limit = Column(Integer, unique=False)
    # ALTER TABLE project_quota ADD COLUMN test_duration_limit INTEGER;
    test_duration_limit = Column(Integer, unique=False, default=-1)
    # ALTER TABLE project_quota ADD COLUMN cpu_limit INTEGER;
    cpu_limit = Column(Integer, unique=False, default=-1)
    # ALTER TABLE project_quota ADD COLUMN memory_limit INTEGER;
    memory_limit = Column(Integer, unique=False, default=-1)
    last_update_time = Column(DateTime, server_default=data_tools.utcnow())
    dast_scans = Column(Integer, unique=False, default=-1)
    sast_scans = Column(Integer, default=-1)
    vcu_hard_limit = Column(Integer, unique=False, nullable=True)
    vcu_soft_limit = Column(Integer, unique=False, nullable=True)
    vcu_limit_total_block = Column(Boolean, unique=False, nullable=False, default=False)
    storage_hard_limit = Column(Integer, unique=False, nullable=True)
    storage_soft_limit = Column(Integer, unique=False, nullable=True)
    storage_limit_total_block = Column(Boolean, unique=False, nullable=False, default=False)

    def update_retention_limit(self, data_retention_limit):
        self.data_retention_limit = data_retention_limit
        self.commit()

    def update_vcu_limits(self, vcu_hard_limit, vcu_soft_limit, vcu_limit_total_block=False):
        self.vcu_hard_limit = vcu_hard_limit
        self.vcu_soft_limit = vcu_soft_limit
        self.vcu_limit_total_block = vcu_limit_total_block
        self.commit()

    def update_storage_limits(self, storage_hard_limit, storage_soft_limit, storage_limit_total_block=False):
        self.storage_hard_limit = storage_hard_limit
        self.storage_soft_limit = storage_soft_limit
        self.storage_limit_total_block = storage_limit_total_block
        self.commit()

    @classmethod
    def update_time(cls, project_quota) -> bool:
        if not project_quota.last_update_time:
            project_quota.last_update_time = datetime.utcnow()
            project_quota.commit()
            return True
        if (datetime.utcnow() - project_quota.last_update_time).total_seconds() > 2592000:
            project_quota.last_update_time = project_quota.last_update_time + timedelta(seconds=2592000)
            statistic = Statistic.query.filter_by(project_id=project_quota.project_id).first()
            statistic.vuh_used = 0
            statistic.dast_scans = 0
            statistic.sast_scans = 0
            statistic.performance_test_runs = 0
            statistic.ui_performance_test_runs = 0
            statistic.commit()
            return True
        return False

    @classmethod
    def check_quota(cls, project_id: int, quota: str) -> bool:
        project_quota = ProjectQuota.query.filter_by(project_id=project_id).first()
        ProjectQuota.update_time(project_quota)
        project_quota = project_quota.to_json()
        if project_quota:
            if project_quota[quota] == -1:
                return True
            statistic = Statistic.query.filter_by(project_id=project_id).first().to_json()
            if statistic[quota] >= project_quota[quota]:
                return False
        return True

    @staticmethod
    def check_quota_json(project_id: int, quota: str):
        if quota:
            return ProjectQuota.check_quota(project_id, quota)
        return ProjectQuota.query.filter(ProjectQuota.project_id == project_id).first().to_json()

    @staticmethod
    def _update_quota(project_id, data_retention_limit, test_duration_limit, cpu_limit, memory_limit, vcu_hard_limit,
                      vcu_soft_limit, vcu_limit_total_block, storage_hard_limit, storage_soft_limit,
                      storage_limit_total_block):
        quota = ProjectQuota.query.filter_by(project_id=project_id).first()
        if quota:
            quota.data_retention_limit = data_retention_limit
            quota.test_duration_limit = test_duration_limit
            quota.cpu_limit = cpu_limit
            quota.memory_limit = memory_limit
            quota.vcu_hard_limit = vcu_hard_limit
            quota.vcu_soft_limit = vcu_soft_limit
            quota.vcu_limit_total_block = vcu_limit_total_block
            quota.storage_hard_limit = storage_hard_limit
            quota.storage_soft_limit = storage_soft_limit
            quota.storage_limit_total_block = storage_limit_total_block
            quota.commit()
        else:
            quota = ProjectQuota(project_id=project_id, data_retention_limit=data_retention_limit,
                                 test_duration_limit=test_duration_limit, cpu_limit=cpu_limit, memory_limit=memory_limit,
                vcu_hard_limit=vcu_hard_limit, vcu_soft_limit=vcu_soft_limit, 
                vcu_limit_total_block=vcu_limit_total_block, storage_hard_limit=storage_hard_limit, 
                storage_soft_limit=storage_soft_limit, storage_limit_total_block=storage_limit_total_block)
            quota.insert()
        return quota

    @staticmethod
    def create(project_id, data_retention_limit, test_duration_limit, cpu_limit, memory_limit, vcu_hard_limit, vcu_soft_limit, vcu_limit_total_block,
            storage_hard_limit, storage_soft_limit, storage_limit_total_block):
        return ProjectQuota._update_quota(project_id=project_id,
            data_retention_limit=data_retention_limit, test_duration_limit=test_duration_limit, cpu_limit=cpu_limit,
                                          memory_limit=memory_limit, vcu_hard_limit=vcu_hard_limit,
            vcu_soft_limit=vcu_soft_limit, vcu_limit_total_block=vcu_limit_total_block,
            storage_hard_limit=storage_hard_limit, storage_soft_limit=storage_soft_limit,
            storage_limit_total_block=storage_limit_total_block)

    @property
    def storage_hard_limit_in_bytes(self) -> Optional[int]:
        try:
            return self.storage_hard_limit * 1_000_000_000
        except TypeError:
            return None
    
    @property
    def storage_soft_limit_in_bytes(self) -> Optional[int]:
        try:
            return self.storage_soft_limit * 1_000_000_000
        except TypeError:
            return None

