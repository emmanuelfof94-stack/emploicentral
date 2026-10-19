from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from core.database import Base


class Wave_checkouts(Base):
    """Session de paiement Wave Checkout (une par tentative d'achat).

    Nouvelle table (le projet n'altère pas les tables existantes) : l'achat n'est
    inscrit dans `course_purchases` (status='paid') qu'une fois le paiement confirmé
    par Wave — webhook signé ou relecture de la session via l'API Wave.
    """

    __tablename__ = "wave_checkouts"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    product_slug = Column(String, nullable=False)         # "pmp", "formations-illimite"…
    amount = Column(String, nullable=False)               # montant XOF envoyé à Wave, ex. "20000"
    session_id = Column(String, nullable=True, index=True)  # "cos-…" renvoyé par Wave
    checkout_status = Column(String, nullable=True)       # open / complete / expired
    payment_status = Column(String, nullable=True)        # processing / cancelled / succeeded
    transaction_id = Column(String, nullable=True)
    purchase_id = Column(Integer, nullable=True)          # ligne course_purchases créée au succès
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
