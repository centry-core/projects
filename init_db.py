# from ..shared.db_manager import Base, engine
from tools import db


def init_db():
    from .models.project import Project
    from .models.quota import ProjectQuota
    from .models.statistics import Statistic

    db.Base.metadata.create_all(bind=db.engine)

