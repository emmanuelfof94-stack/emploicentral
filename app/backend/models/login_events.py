from models.base import Base
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func


class LoginEvent(Base):
    """Trace d'une connexion réussie : d'où (IP / lieu) et avec quel appareil.

    Une ligne est ajoutée à chaque connexion (login local, inscription, OIDC) afin de
    garder un historique « appareils & lieux » par utilisateur, à la manière de la
    page « activité de connexion » d'un compte Google. L'écriture se fait en tâche de
    fond : elle ne ralentit ni ne casse jamais la connexion.
    """

    __tablename__ = "login_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(255), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # D'où : IP réelle (derrière proxy) + lieu approximatif déduit de l'IP.
    ip = Column(String(64), nullable=True)
    country = Column(String(80), nullable=True)
    city = Column(String(120), nullable=True)

    # Avec quel appareil : déduit du User-Agent.
    device = Column(String(40), nullable=True)   # Mobile / Ordinateur / Tablette
    os = Column(String(60), nullable=True)       # Android, iOS, Windows, macOS…
    browser = Column(String(60), nullable=True)  # Chrome, Safari, Firefox…
    user_agent = Column(String(400), nullable=True)

    # Comment : "local" (email/mot de passe), "register" (inscription) ou "platform" (OIDC).
    auth_type = Column(String(20), nullable=True)
