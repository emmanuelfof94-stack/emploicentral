from core.database import Base
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint


class Storage_objects(Base):
    """Propriétaire de chaque fichier déposé (CV…). Registre de contrôle d'accès du
    stockage : sans lui, n'importe quel compte pouvait lister, lire, remplacer ou
    supprimer les fichiers des autres (faille critique du test d'intrusion 2026-10-19).

    `bucket` / `object_key` sont stockés sous leur forme assainie (identique au nom
    réel sur disque), pour qu'une variante d'écriture ne contourne pas le contrôle.
    """

    __tablename__ = "storage_objects"
    __table_args__ = (
        UniqueConstraint("bucket", "object_key", name="uq_storage_objects_bucket_key"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    bucket = Column(String, nullable=False)
    object_key = Column(String, nullable=False)
    owner_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
