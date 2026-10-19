"""Cloisonnement du stockage de fichiers (CV) et des offres non validées.

Rejoue les attaques du test d'intrusion du 2026-10-19 :
- [CRITIQUE] un candidat listait, téléchargeait, remplaçait et supprimait les CV des autres ;
- variante : pointer son profil vers le CV d'un autre pour que la génération de CV le lise ;
- [MOYENNE] les offres recruteur en attente de modération étaient lisibles sans connexion.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from models.auth import User
from models.job_offers import Job_offers
from models.job_postings import Job_postings
from models.user_profiles import User_profiles
from services import local_storage
from tests.conftest import auth_headers, make_token

CV = b"%PDF-1.4 CV de C1 : nom, telephone, parcours"


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(local_storage, "STORAGE_ROOT", tmp_path)


@pytest.fixture
async def users(db_session):
    for uid, role in [("c1", "user"), ("c2", "user"), ("adm", "admin")]:
        db_session.add(User(id=uid, email=f"{uid}@x.ci", role=role))
    await db_session.commit()
    return {uid: auth_headers(make_token(uid, f"{uid}@x.ci", role)) for uid, role in
            [("c1", "user"), ("c2", "user"), ("adm", "admin")]}


async def _upload(client, headers, key="cv_1_mon cv.pdf", body=CV):
    r = await client.post("/api/v1/storage/upload-url", headers=headers,
                          json={"bucket_name": "cvs", "object_key": key})
    if r.status_code != 200:
        return r
    u = urlsplit(r.json()["upload_url"])
    return await client.put(f"{u.path}?{u.query}", content=body)


async def test_owner_can_upload_and_download_own_cv(client, users):
    assert (await _upload(client, users["c1"])).status_code == 200
    r = await client.post("/api/v1/storage/download-url", headers=users["c1"],
                          json={"bucket_name": "cvs", "object_key": "cv_1_mon cv.pdf"})
    assert r.status_code == 200
    u = urlsplit(r.json()["download_url"])
    assert (await client.get(f"{u.path}?{u.query}")).content == CV


async def test_other_user_cannot_list_read_overwrite_or_delete(client, users):
    await _upload(client, users["c1"])
    key = {"bucket_name": "cvs", "object_key": "cv_1_mon cv.pdf"}

    r = await client.get("/api/v1/storage/list-objects", headers=users["c2"], params={"bucket_name": "cvs"})
    assert r.status_code == 403
    assert (await client.get("/api/v1/storage/list-buckets", headers=users["c2"])).status_code == 403
    assert (await client.post("/api/v1/storage/download-url", headers=users["c2"], json=key)).status_code == 404
    assert (await client.get("/api/v1/storage/get-object-info", headers=users["c2"], params=key)).status_code == 404
    assert (await client.request("DELETE", "/api/v1/storage/delete-object", headers=users["c2"], json=key)).status_code == 404
    r = await client.post("/api/v1/storage/rename-object", headers=users["c2"],
                          json={"bucket_name": "cvs", "source_key": key["object_key"], "target_key": "vol.pdf"})
    assert r.status_code == 404
    # Écraser : même clé, ou variante qui retombe sur le même fichier après assainissement.
    assert (await _upload(client, users["c2"], body=b"pirate")).status_code == 409
    assert (await _upload(client, users["c2"], key="../cv_1_mon cv.pdf", body=b"pirate")).status_code == 409

    # Le fichier de C1 est intact.
    path = local_storage.read_blob_path("cvs", key["object_key"])
    assert path is not None and path.read_bytes() == CV


async def test_owner_can_rename_and_delete(client, users):
    await _upload(client, users["c1"])
    r = await client.post("/api/v1/storage/rename-object", headers=users["c1"],
                          json={"bucket_name": "cvs", "source_key": "cv_1_mon cv.pdf", "target_key": "cv_final.pdf"})
    assert r.status_code == 200
    key = {"bucket_name": "cvs", "object_key": "cv_final.pdf"}
    assert (await client.post("/api/v1/storage/download-url", headers=users["c1"], json=key)).status_code == 200
    assert (await client.post("/api/v1/storage/download-url", headers=users["c2"], json=key)).status_code == 404
    assert (await client.request("DELETE", "/api/v1/storage/delete-object", headers=users["c1"], json=key)).status_code == 200
    assert local_storage.read_blob_path("cvs", "cv_final.pdf") is None
    # La clé libérée peut être réutilisée par quelqu'un d'autre.
    assert (await _upload(client, users["c2"], key="cv_final.pdf")).status_code == 200


async def test_legacy_file_without_owner_is_locked(client, users):
    local_storage.save_blob("cvs", "ancien.pdf", CV)  # déposé avant le registre
    key = {"bucket_name": "cvs", "object_key": "ancien.pdf"}
    assert (await client.post("/api/v1/storage/download-url", headers=users["c2"], json=key)).status_code == 404
    assert (await _upload(client, users["c2"], key="ancien.pdf")).status_code == 409
    # L'admin garde l'accès (support, suppression).
    assert (await client.post("/api/v1/storage/download-url", headers=users["adm"], json=key)).status_code == 200
    assert (await client.get("/api/v1/storage/list-objects", headers=users["adm"],
                             params={"bucket_name": "cvs"})).status_code == 200


async def test_profile_cannot_point_to_someone_elses_cv(client, db_session, users):
    await _upload(client, users["c1"])
    r = await client.post("/api/v1/entities/user_profiles", headers=users["c2"],
                          json={"full_name": "C2", "cv_object_key": "cv_1_mon cv.pdf"})
    assert r.status_code == 400

    r = await client.post("/api/v1/entities/user_profiles", headers=users["c2"], json={"full_name": "C2"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = await client.put(f"/api/v1/entities/user_profiles/{pid}", headers=users["c2"],
                         json={"cv_object_key": "cv_1_mon cv.pdf"})
    assert r.status_code == 400

    # Son propre CV : accepté.
    await _upload(client, users["c2"], key="cv_2.pdf")
    r = await client.put(f"/api/v1/entities/user_profiles/{pid}", headers=users["c2"],
                         json={"cv_object_key": "cv_2.pdf"})
    assert r.status_code == 200 and r.json()["cv_object_key"] == "cv_2.pdf"


async def test_profile_keeps_existing_legacy_cv_key_on_save(client, db_session, users):
    # Profil existant pointant vers un CV d'avant le registre : réenregistrer le profil
    # (le front renvoie toujours cv_object_key) ne doit pas échouer.
    db_session.add(User_profiles(id=50, user_id="c1", full_name="C1", cv_object_key="ancien.pdf"))
    await db_session.commit()
    r = await client.put("/api/v1/entities/user_profiles/50", headers=users["c1"],
                         json={"full_name": "C1 bis", "cv_object_key": "ancien.pdf"})
    assert r.status_code == 200


async def test_unapproved_recruiter_offers_are_hidden(client, db_session):
    db_session.add_all([
        Job_offers(id=1, title="Approuvée", company="A", is_active=True, source="Recruteur"),
        Job_offers(id=2, title="En attente", company="A", is_active=False, source="Recruteur"),
        Job_offers(id=3, title="Agrégée", company="B", is_active=True, source="Emploi.ci"),
    ])
    db_session.add_all([
        Job_postings(job_id=1, posted_by="r", status="approved"),
        Job_postings(job_id=2, posted_by="r", status="pending"),
    ])
    await db_session.commit()

    for url in ("/api/v1/entities/job_offers", "/api/v1/entities/job_offers/all"):
        body = (await client.get(url, params={"limit": 50})).json()
        assert sorted(j["id"] for j in body["items"]) == [1, 3]
        assert body["total"] == 2
    assert (await client.get("/api/v1/entities/job_offers/2")).status_code == 404
    assert (await client.get("/api/v1/entities/job_offers/1")).status_code == 200
