# !/usr/bin/python3
# coding=utf-8

#   Copyright 2022 getcarrier.io
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# """ DB migration """

revision = "202308011522"
down_revision = "202303051207"
branch_labels = None


from alembic import op
import sqlalchemy as sa


table_name = "project_quota"

def upgrade(module, payload):
    op.add_column(table_name, sa.Column('vcu_hard_limit', sa.Integer(), unique=False, nullable=True))
    op.add_column(table_name, sa.Column('vcu_soft_limit', sa.Integer(), unique=False, nullable=True))
    op.add_column(table_name, sa.Column('vcu_limit_total_block', sa.Boolean(), unique=False, nullable=False, default=False))
    op.add_column(table_name, sa.Column('storage_hard_limit', sa.Integer(), unique=False, nullable=True))
    op.add_column(table_name, sa.Column('storage_soft_limit', sa.Integer(), unique=False, nullable=True))
    op.add_column(table_name, sa.Column('storage_limit_total_block', sa.Boolean(), unique=False, nullable=False, default=False))
    op.drop_column(table_name, "vuh_limit")
    op.drop_column(table_name, "storage_space")


def downgrade(module, payload):
    op.drop_column(table_name, "vcu_hard_limit")
    op.drop_column(table_name, "vcu_soft_limit")
    op.drop_column(table_name, "vcu_limit_total_block")
    op.drop_column(table_name, "storage_hard_limit")
    op.drop_column(table_name, "storage_soft_limit")
    op.drop_column(table_name, "storage_limit_total_block")
    op.add_column(table_name, sa.Column('vuh_limit', sa.Integer(), nullable=False, default=60000))
    op.add_column(table_name, sa.Column('storage_space', sa.Integer(), default=1_000_000_000))
