from datetime import datetime

from sqlalchemy import Column, DateTime, String

from core.database import Base


class App_markers(Base):
    """Petits marqueurs persistants (clé → valeur), ex. version des règles de secteur
    déjà appliquée en base, pour ne lancer une migration de données qu'UNE fois."""

    __tablename__ = "app_markers"
    __table_args__ = {"extend_existing": True}

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
