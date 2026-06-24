from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from core.database import Base


class Training_partners(Base):
    """Organisme de formation partenaire affiché aux candidats.

    Géré par l'admin (CRUD). Les partenaires sont présentés dans un annuaire et
    suggérés automatiquement sous chaque parcours généré, selon la correspondance
    entre `domains` (thématiques couvertes) et la thématique demandée.
    `pricing` vaut "free" (gratuit) ou "paid" (payant).
    """

    __tablename__ = "training_partners"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)                 # site du partenaire
    description = Column(Text, nullable=True)
    domains = Column(String, nullable=True)              # thématiques couvertes, séparées par des virgules
    pricing = Column(String, nullable=False, default="paid")  # "free" | "paid"
    logo_url = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    location = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
