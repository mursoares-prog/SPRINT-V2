"""Carrega o histórico do changeLog.json (frontend) na tabela change_log.

Idempotente: se a tabela já tiver entradas, não faz nada. Roda a partir de backend/.
  python seed_changelog.py
"""
import json
from pathlib import Path

from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app.models import ChangeLogEntry

# Prefere a cópia local do backend (app/data, robusta em deploy standalone);
# cai para o changeLog.json do frontend (dev, repos no mesmo diretório pai).
_LOCAL = Path(__file__).resolve().parent / "app" / "data" / "change_log.json"
_FRONT = Path(__file__).resolve().parent.parent / "abandono-app" / "src" / "data" / "changeLog.json"


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.execute(select(func.count(ChangeLogEntry.id))).scalar() or 0
        if existing:
            print(f"change_log já tem {existing} entradas — nada a fazer.")
            return
        source = _LOCAL if _LOCAL.exists() else _FRONT
        if not source.exists():
            print(f"Fonte não encontrada: {_LOCAL} nem {_FRONT}")
            return
        entries = json.loads(source.read_text(encoding="utf-8-sig"))
        for e in entries:
            db.add(ChangeLogEntry(
                id=e["id"], data=e["data"], pacote=e["pacote"], linha=e.get("linha"),
                tipo=e["tipo"], resumo=e["resumo"], antes=e.get("antes"), depois=e.get("depois"),
                author=None,
            ))
        db.commit()
        print(f"Importadas {len(entries)} entradas historicas para change_log.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
