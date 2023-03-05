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

revision = "202303051207"
down_revision = None
branch_labels = None


from alembic import op
import sqlalchemy as sa


table_name = "project_quota"

def upgrade(module, payload):
    op.add_column(table_name, sa.Column('sast_scans', sa.Integer(), server_default=str(-1)))


def downgrade(module, payload):
    op.drop_column(table_name, "sast_scans")
