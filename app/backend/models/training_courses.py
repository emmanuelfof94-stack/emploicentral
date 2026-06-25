from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from core.database import Base


class Training_courses(Base):
    """Formation concrète d'un catalogue, rattachée (souplement) à un partenaire.

    Distincte des parcours générés par IA (`training_requests`) : ici ce sont de
    vraies offres de formation saisies par l'admin, que le candidat parcourt et
    choisit. Le lien au partenaire est volontairement souple (`partner_id` simple
    entier + `partner_name` dénormalisé pour l'affichage), sans contrainte FK dure
    — cohérent avec le reste du schéma.
    `domain` sert au filtrage et à la suggestion par thématique. `is_free` pilote
    le tri « gratuit d'abord » comme pour les partenaires.
    """

    __tablename__ = "training_courses"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    partner_id = Column(Integer, nullable=True, index=True)   # -> training_partners.id (souple)
    partner_name = Column(String, nullable=True)              # dénormalisé pour l'affichage
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String, nullable=True)                   # thématique / catégorie
    level = Column(String, nullable=True)                    # Débutant / Intermédiaire / Avancé / Tous niveaux
    duration = Column(String, nullable=True)                 # ex. "3 jours", "40 h"
    price = Column(String, nullable=True)                    # ex. "150 000 FCFA" (libre)
    is_free = Column(Boolean, default=False, nullable=False)
    format = Column(String, nullable=True)                   # Présentiel / En ligne / Hybride
    location = Column(String, nullable=True)
    url = Column(String, nullable=True)                      # lien d'inscription / détails
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
