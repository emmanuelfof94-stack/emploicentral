from datetime import datetime

from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, String


class PageView(Base):
    """Une vue de page (analytics intégré).

    Respectueux de la vie privée : aucune IP brute n'est stockée. ``visitor_hash``
    est un hachage anonyme et quotidien (sel + IP + user-agent + date) qui permet
    de compter les visiteurs uniques sans identifiant persistant ni cookie.
    """

    __tablename__ = "page_views"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now, index=True)
    path = Column(String, nullable=False, index=True)
    # Host du référent (ex. "google.com"). Vide = accès direct.
    referrer = Column(String, nullable=True)
    # Hash anonyme du visiteur (rotation quotidienne) — pas d'IP en clair.
    visitor_hash = Column(String, nullable=True, index=True)
    user_agent = Column(String, nullable=True)
    is_bot = Column(Boolean, nullable=False, default=False, index=True)
