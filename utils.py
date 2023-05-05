# from abc import ABC, abstractmethod
# from typing import Tuple, Optional
#
# from datetime import datetime
# from sqlalchemy import schema
#
# from .constants import INFLUX_DATABASES, PROJECT_USER_EMAIL_TEMPLATE, PROJECT_USER_NAME_TEMPLATE, \
#     PROJECT_SCHEMA_TEMPLATE
# from .models.pd.project import ProjectCreatePD
# from .models.project import Project
# from .models.statistics import Statistic
# from .models.quota import ProjectQuota
# from .tools.influx_tools import get_client
# from .tools.rabbit_tools import create_project_user_and_vhost
#
# from pylon.core.tools import log
# from tools import VaultClient, auth, constants as c, db



# def create_project_influx_databases(project_id: int) -> None:
#
#
#
# def drop_project_influx_databases(project_id: int) -> None:
#





# def create_project_user(project_id: int) -> int:
#     # Auth: create project user
#     user = get_project_user(project_id)
#     if user:
#         return user['id']
#     user_name = PROJECT_USER_NAME_TEMPLATE.format(project_id)
#     user_email = PROJECT_USER_EMAIL_TEMPLATE.format(project_id)
#     user_id = auth.add_user(user_email, user_name)
#     auth.assign_user_to_role(user_id, "system", mode='administration')
#     return user_id
#
#
# def delete_project_user(project_id: int) -> int:
#     user = get_project_user(project_id)
#     assert user, f'project user {project_id} not found'
#     auth.auth_delete_user(user['id'])
#     return user['id']


# def create_project_token(user_id: int) -> str:
#     # Auth: add project token
#     all_tokens = auth.list_tokens(user_id)
#     #
#     if len(all_tokens) < 1:
#         token_id = auth.add_token(
#             user_id, "api",
#             # expires=datetime.datetime.now()+datetime.timedelta(seconds=30),
#         )
#     else:
#         token_id = all_tokens[0]["id"]
#     #
#     return auth.encode_token(token_id)
#
#
# def delete_project_token(user_id: int) -> None:
#     for i in auth.list_tokens(user_id):
#         auth.delete_token(i['id'])





# def create_project_model(pd_model: ProjectCreatePD, owner_id: int) -> Project:
#     project = Project(
#         name=pd_model.name,
#         plugins=pd_model.plugins,
#         owner_id=owner_id
#     )
#     project.insert()
#     log.info('after project.insert()')
#     ProjectQuota.create(
#         project_id=project.id,
#         vuh_limit=pd_model.vuh_limit,
#         storage_space=pd_model.storage_space_limit,
#         data_retention_limit=pd_model.data_retention_limit
#     )
#     log.info('after quota created')
#
#     statistic = Statistic(
#         project_id=project.id,
#         start_time=str(datetime.utcnow()),
#     )
#     statistic.insert()
#     log.info('after statistic created')
#     return project
#
#
# def delete_project_model(project_id: int, commit: bool = True) -> None:
#     Statistic.query.filter(Statistic.project_id == project_id).delete()
#     if commit:
#         Statistic.commit()
#     log.info('statistic deleted')
#
#     ProjectQuota.query.filter(ProjectQuota.project_id == project_id).delete()
#     if commit:
#         ProjectQuota.commit()
#     log.info('quota deleted')
#
#     # Project.query.get(project_id).delete()
#     Project.apply_full_delete_by_pk(pk=project_id)
#     if commit:
#         Project.commit()
#     log.info('project deleted')


# def create_project_schema(project_id: int) -> None:
#     with db.with_project_schema_session(project_id) as tenant_db:
#         tenant_db.execute(schema.CreateSchema(PROJECT_SCHEMA_TEMPLATE.format(project_id)))
#         db.get_tenant_specific_metadata().create_all(bind=tenant_db.connection())
#         tenant_db.commit()
#     log.info("Project schema created")
#
#
# def delete_project_schema(project_id: int) -> None:
#     with db.with_project_schema_session(project_id) as tenant_db:
#         tenant_db.execute(schema.DropSchema(PROJECT_SCHEMA_TEMPLATE.format(project_id)))
#         db.get_tenant_specific_metadata().drop_all(bind=tenant_db.connection())
#         tenant_db.commit()
#     log.info("Project schema deleted")



# class AdditionalDatabases(ProjectCreationStep):
# additional_databases = ProjectCreationStep('additional_databases', create=)

# def create_additional_databases(project_id: int)
#     create_project_user_and_vhost(vault_client.project_id)
#     log.info('after create_project_user_and_vhost')
#     create_project_influx_databases(vault_client.project_id)
#     log.info('after create_project_influx_databases')



# def create_project_secrets(vault_client: 'VaultClient', auth_token: str):
#     project_secrets, project_hidden_secrets = generate_project_secrets(vault_client.project_id)
#     project_secrets["auth_token"] = auth_token
#
#     vault_client.set_project_secrets(project_secrets)
#     log.info('after set_project_secrets')
#     vault_client.set_project_hidden_secrets(project_hidden_secrets)
#     log.info('after set_project_hidden_secrets')



# def delete_project_secrets(project_id):
#     delete_project_user_and_vhost(vault_client.project_id)
#     log.info('after create_project_user_and_vhost')
#     delete_project_influx_databases(vault_client.project_id)
#     log.info('after create_project_influx_databases')
