from tools import db


def init_db():
    from .models.project import Project
    from .models.quota import ProjectQuota
    from .models.statistics import Statistic

    db.get_shared_metadata().create_all(bind=db.engine)

