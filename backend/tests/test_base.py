"""Testes da edição da base de linhas (overrides, validação de tokens, log, papéis)."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.base_data import package_lines
from app.database import Base, get_db
from app.models import ChangeLogEntry
from app.routers.auth import router as auth_router
from app.routers.base import router as base_router
from app.routers.changelog import router as changelog_router

# Um pacote/linha real da base bundled.
_PL = package_lines()
PKG = next(k for k, v in _PL.items() if v and v[0].get("text"))
IDX = 0
ORIG = _PL[PKG][0]["text"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    users = {"ed": {"passwordHash": hash_password("p"), "role": "admin"},
             "vw": {"passwordHash": hash_password("p"), "role": "projetista"}}
    uf = tmp_path / "users.json"
    uf.write_text(json.dumps(users), encoding="utf-8")
    monkeypatch.setenv("AUTH_USERS_FILE", str(uf))

    def override_get_db():
        d = TestSession()
        try:
            yield d
        finally:
            d.close()

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(base_router)
    app.include_router(changelog_router)
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c._session = TestSession  # type: ignore[attr-defined]
    return c


def _token(client, user):
    return client.post("/api/auth/login", json={"username": user, "password": "p"}).json()["token"]


def _hdr(client, user):
    return {"Authorization": f"Bearer {_token(client, user)}"}


def test_get_merged_base(client):
    r = client.get("/api/base/package-lines")
    assert r.status_code == 200
    assert PKG in r.json()


def test_get_fields(client):
    r = client.get("/api/base/fields")
    assert r.status_code == 200
    fields = r.json()
    assert "prof" in fields  # PLAN_KEY


def test_admin_edits_line_and_logs(client):
    new_text = ORIG + " {{prof=XXX}}"  # token valido (prof e' PLAN_KEY)
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": new_text}, headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json()["text"] == new_text
    # base mesclada reflete a edição
    assert client.get("/api/base/package-lines").json()[PKG][IDX]["text"] == new_text
    # registrou no changelog com autor
    log = client.get("/api/changelog").json()
    assert log and log[0]["pacote"] == PKG and log[0]["author"] == "ed" and log[0]["linha"] == IDX + 1


def test_reject_invalid_token(client):
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}",
                   json={"text": ORIG + " {{zzznaoexiste=XXX}}"}, headers=_hdr(client, "ed"))
    assert r.status_code == 400
    assert "zzznaoexiste" in r.json()["detail"]


def test_projetista_cannot_edit(client):
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": ORIG + " x"}, headers=_hdr(client, "vw"))
    assert r.status_code == 403


def test_anonymous_cannot_edit(client):
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": ORIG + " x"})
    assert r.status_code == 401


def test_reset_reverts(client):
    client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": ORIG + " {{prof=XXX}}"}, headers=_hdr(client, "ed"))
    r = client.delete(f"/api/base/package-lines/{PKG}/{IDX}", headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json()["reverted"] is True
    assert client.get("/api/base/package-lines").json()[PKG][IDX]["text"] == ORIG


def test_unknown_package_404(client):
    r = client.put("/api/base/package-lines/NAO_EXISTE/0", json={"text": "x"}, headers=_hdr(client, "ed"))
    assert r.status_code == 404


def test_edit_duration_and_ontology_merges(client):
    patch = {"duration": 3.5, "owFase": "AP. 1A", "owAtividade": "X", "owOperacao": "Y", "owEtapa": "Z"}
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json=patch, headers=_hdr(client, "ed"))
    assert r.status_code == 200
    merged = client.get("/api/base/package-lines").json()[PKG][IDX]
    assert merged["duration"] == 3.5
    assert merged["owFase"] == "AP. 1A" and merged["owEtapa"] == "Z"
    # texto preservado (patch parcial não tocou no texto)
    assert merged["text"] == ORIG


def test_rec_pad_only_in_overrides_not_in_package_lines(client):
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}",
                   json={"rec": "Recomendo X", "pad": "NORMA-123"}, headers=_hdr(client, "ed"))
    assert r.status_code == 200
    ov = next(o for o in client.get("/api/base/overrides").json()
              if o["pkgId"] == PKG and o["lineIndex"] == IDX)
    assert ov["rec"] == "Recomendo X" and ov["pad"] == "NORMA-123"
    # rec/pad não pertencem a package_lines (mesclados no front sobre os detalhes)
    assert "rec" not in client.get("/api/base/package-lines").json()[PKG][IDX]


def test_noop_patch_is_unchanged(client):
    client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"duration": 7.0}, headers=_hdr(client, "ed"))
    r = client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"duration": 7.0}, headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json().get("unchanged") is True


# ── Edição estrutural por pacote (linhas completas) ────────────────────────────

def _line(text, **kw):
    base = {"text": text, "duration": 0, "bop": None, "compensando": None,
            "isContingency": None, "isParallel": None, "owFase": "AP. 0",
            "owAtividade": "", "owOperacao": "", "owEtapa": "",
            "genOperacao": None, "genOperacaoDual": None, "rec": "", "pad": ""}
    base.update(kw)
    return base


def test_save_package_lines_add_delete_reorder(client):
    lines = [_line("Linha A", duration=1.5, rec="Rec A", pad="Pad A"),
             _line("Linha B nova", duration=2.0)]
    r = client.put(f"/api/base/packages/{PKG}/lines", json={"lines": lines}, headers=_hdr(client, "ed"))
    assert r.status_code == 200
    merged = client.get("/api/base/package-lines").json()[PKG]
    assert len(merged) == 2
    assert merged[0]["text"] == "Linha A" and merged[0]["duration"] == 1.5
    assert merged[1]["text"] == "Linha B nova"
    # rec/pad NÃO entram em package-lines (são detalhes, mesclados no front)
    assert "rec" not in merged[0]
    # ... mas voltam pelo /package-overrides
    ov = next(o for o in client.get("/api/base/package-overrides").json() if o["pkgId"] == PKG)
    assert ov["lines"][0]["rec"] == "Rec A" and ov["lines"][0]["pad"] == "Pad A"


def test_package_override_takes_precedence_over_line_override(client):
    client.put(f"/api/base/package-lines/{PKG}/{IDX}", json={"text": ORIG + " X"}, headers=_hdr(client, "ed"))
    client.put(f"/api/base/packages/{PKG}/lines", json={"lines": [_line("Só esta")]}, headers=_hdr(client, "ed"))
    merged = client.get("/api/base/package-lines").json()[PKG]
    assert len(merged) == 1 and merged[0]["text"] == "Só esta"


def test_reset_package_lines_reverts_bundle(client):
    n_orig = len(client.get("/api/base/package-lines").json()[PKG])
    client.put(f"/api/base/packages/{PKG}/lines", json={"lines": [_line("x")]}, headers=_hdr(client, "ed"))
    r = client.delete(f"/api/base/packages/{PKG}/lines", headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json()["reverted"] is True
    assert len(client.get("/api/base/package-lines").json()[PKG]) == n_orig


def test_save_package_rejects_invalid_token(client):
    r = client.put(f"/api/base/packages/{PKG}/lines",
                   json={"lines": [_line("oi {{zzznaoexiste=XXX}}")]}, headers=_hdr(client, "ed"))
    assert r.status_code == 400 and "zzznaoexiste" in r.json()["detail"]


def test_create_duplicate_edit_delete_custom_package(client):
    # cria
    r = client.post("/api/base/packages",
                    json={"name": "Meu pacote", "category": "Custom", "technology": "wireline",
                          "lines": [_line("Linha custom")]}, headers=_hdr(client, "ed"))
    assert r.status_code == 200
    pid = r.json()["pkgId"]
    assert pid.startswith("ABAN")
    # aparece em /packages e nas linhas mescladas
    assert any(m["pkgId"] == pid for m in client.get("/api/base/packages").json())
    assert client.get("/api/base/package-lines").json()[pid][0]["text"] == "Linha custom"
    # edita meta
    r = client.patch(f"/api/base/packages/{pid}", json={"name": "Renomeado"}, headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json()["name"] == "Renomeado"
    # apaga
    r = client.delete(f"/api/base/packages/{pid}", headers=_hdr(client, "ed"))
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert pid not in client.get("/api/base/package-lines").json()


def test_bundle_package_meta_locked_and_undeletable(client):
    assert client.patch(f"/api/base/packages/{PKG}", json={"name": "x"}, headers=_hdr(client, "ed")).status_code == 400
    assert client.delete(f"/api/base/packages/{PKG}", headers=_hdr(client, "ed")).status_code == 400


def test_custom_package_endpoints_require_admin(client):
    assert client.post("/api/base/packages", json={"name": "x"}, headers=_hdr(client, "vw")).status_code == 403
    assert client.put(f"/api/base/packages/{PKG}/lines", json={"lines": []}).status_code == 401
