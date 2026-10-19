"""Contrôle d'accès du stockage de fichiers : chaque objet appartient à un utilisateur.

Règles (les admins passent partout) :
- déposer (`claim`) : clé libre → elle devient la propriété de l'appelant ; clé déjà
  à lui → OK (remplacement de son propre fichier) ; clé d'un autre, ou fichier déjà
  présent sur disque sans propriétaire connu (antérieur au registre) → refus ;
- lire / renommer / supprimer (`require_owner`) : uniquement son propre fichier.
  Un fichier sans propriétaire enregistré est refusé (fail closed).
Les refus renvoient 404 pour ne pas révéler l'existence d'un fichier d'autrui.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.storage_objects import Storage_objects
from schemas.auth import UserResponse
from services.local_storage import read_blob_path, sanitize_bucket, sanitize_key

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier introuvable")


def is_admin(user: UserResponse) -> bool:
    return user.role == "admin"


def normalize(bucket: str, key: str) -> tuple:
    return sanitize_bucket(bucket), sanitize_key(key)


async def owner_of(db: AsyncSession, bucket: str, key: str) -> Optional[str]:
    b, k = normalize(bucket, key)
    return (await db.execute(
        select(Storage_objects.owner_id).where(Storage_objects.bucket == b, Storage_objects.object_key == k)
    )).scalar()


def _exists_on_disk(bucket: str, key: str) -> bool:
    try:
        return read_blob_path(bucket, key) is not None
    except ValueError:
        return False


async def claim(db: AsyncSession, user: UserResponse, bucket: str, key: str) -> None:
    """Réserve `bucket/key` pour l'appelant avant d'émettre une URL d'envoi."""
    uid = str(user.id)
    owner = await owner_of(db, bucket, key)
    if owner == uid or (owner and is_admin(user)):
        return
    if owner is not None or _exists_on_disk(bucket, key):
        # Clé d'autrui, ou fichier hérité sans propriétaire : on ne laisse pas écraser.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce nom de fichier est déjà utilisé.")
    b, k = normalize(bucket, key)
    db.add(Storage_objects(bucket=b, object_key=k, owner_id=uid))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if await owner_of(db, bucket, key) != uid:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce nom de fichier est déjà utilisé.")


async def require_owner(db: AsyncSession, user: UserResponse, bucket: str, key: str) -> None:
    if is_admin(user):
        return
    if await owner_of(db, bucket, key) != str(user.id):
        raise NOT_FOUND


async def release(db: AsyncSession, bucket: str, key: str) -> None:
    b, k = normalize(bucket, key)
    row = (await db.execute(
        select(Storage_objects).where(Storage_objects.bucket == b, Storage_objects.object_key == k)
    )).scalars().first()
    if row:
        await db.delete(row)
        await db.commit()


async def transfer_key(db: AsyncSession, bucket: str, old_key: str, new_key: str) -> None:
    b, old_k = normalize(bucket, old_key)
    _, new_k = normalize(bucket, new_key)
    row = (await db.execute(
        select(Storage_objects).where(Storage_objects.bucket == b, Storage_objects.object_key == old_k)
    )).scalars().first()
    if row:
        row.object_key = new_k
        await db.commit()


async def user_owns_cv_key(db: AsyncSession, user_id: str, key: str) -> bool:
    """La clé de CV enregistrée dans un profil doit désigner un fichier de l'utilisateur."""
    return await owner_of(db, "cvs", key) == user_id
