from typing import Optional, Tuple

from ..constants import PROJECT_USER_EMAIL_TEMPLATE, INFLUX_DATABASES

from tools import auth, constants as c


def get_project_user(project_id: int) -> Optional[dict]:
    user_email = PROJECT_USER_EMAIL_TEMPLATE.format(project_id)
    return auth.get_user(email=user_email)


def generate_project_secrets(project_id: int) -> Tuple[dict, dict]:
    project_secrets = {
        'project_id': project_id,
    }

    project_hidden_secrets = {
        k: v.format(project_id) for k, v in INFLUX_DATABASES.items()
    }

    return project_secrets, project_hidden_secrets

