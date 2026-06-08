# SPRINT ABAN — Backend (FastAPI)

API de persistência de projetos. SQLite em dev; trocável por Turso/Postgres no
deploy apenas mudando `DATABASE_URL`.

## Rodar localmente (Windows / PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # ajuste se necessário
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Docs interativas (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/api/health

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET    | `/api/health`          | Status do serviço |
| GET    | `/api/projects`        | Lista resumida de projetos |
| GET    | `/api/projects/{id}`   | Projeto completo (ProjectFile + id) |
| POST   | `/api/projects`        | Cria projeto (body = ProjectFile) |
| PUT    | `/api/projects/{id}`   | Atualiza projeto |
| DELETE | `/api/projects/{id}`   | Remove projeto |

## Estrutura

```
backend/
  app/
    main.py        # app FastAPI, CORS, health
    config.py      # env (DATABASE_URL, CORS_ORIGINS)
    database.py    # engine/sessão SQLAlchemy
    models.py      # modelo Project (documento em coluna JSON)
    schemas.py     # Pydantic (entrada/saída)
    routers/
      projects.py  # CRUD de projetos
  requirements.txt
  .env.example
```

## Deploy (depois)

A escolha do serviço gerenciado fica para a etapa de deploy. Basta apontar
`DATABASE_URL` para o banco hospedado:

- **Turso** (SQLite): `sqlite+libsql://<host>?authToken=...` (requer `sqlalchemy-libsql`)
- **Neon/Postgres**: `postgresql+psycopg://user:pass@host/db` (requer `psycopg`)
