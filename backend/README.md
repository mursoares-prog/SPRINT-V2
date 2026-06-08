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
python seed_auth.py           # cria auth_users.json (teste/teste123 editor, viewer/viewer123)
python seed_changelog.py      # importa o historico do changeLog.json para o banco (1x)
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
| POST   | `/api/schedule`        | Gera o cronograma autoritativo a partir de `{inputs}` (espelho Python do engine) |
| POST   | `/api/schedule/validate` | Compara `{inputs, schedule}` com o cronograma recalculado e reporta divergências |
| POST   | `/api/auth/login`      | Login `{username, password}` → `{token, role, username}` |
| GET    | `/api/auth/me`         | Identidade do token (`Authorization: Bearer <token>`) |
| GET    | `/api/changelog`       | Log de alterações (mais recentes primeiro) |
| POST   | `/api/changelog`       | Acrescenta uma entrada (append-only, **requer editor**) |
| GET    | `/api/base/package-lines` | Base das linhas mesclada (bundled + overrides) |
| GET    | `/api/base/fields`     | Campos válidos para tokens `{{campo=glifo}}` |
| PUT    | `/api/base/package-lines/{pkgId}/{idx}` | Edita o texto de uma linha (**editor**; valida tokens; registra no log) |
| DELETE | `/api/base/package-lines/{pkgId}/{idx}` | Reverte a linha ao original (**editor**) |

O POST/PUT de projetos também retorna um campo `validation` (informativo, nunca
bloqueia o save) com a comparação entre o cronograma salvo e o recalculado dos inputs.

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

## Autenticação e papéis

Usuários ficam em `auth_users.json` (gitignored; veja `auth_users.example.json`),
com papel `editor` (pode editar a base) ou `viewer` (só leitura). Senhas em
PBKDF2-SHA256; token de sessão assinado com HMAC (sem dependências externas).

```powershell
python seed_auth.py                       # cria os usuários padrão
python seed_auth.py joao senha123 editor  # adiciona/atualiza um usuário
```

Sem backend acessível, o front cai no login legado offline (`teste/teste123`, papel viewer).

## Deploy (produção)

Há um `Dockerfile` host-agnóstico (Railway / Render / Fly). O SQLite precisa de
um **volume persistente** (senão o arquivo some a cada restart) — ou troque para
Turso/Postgres via `DATABASE_URL`.

### Variáveis de ambiente

| Var | Obrigatória | Exemplo / default |
|-----|-------------|-------------------|
| `AUTH_SECRET` | **sim** | string aleatória longa (assina os tokens) |
| `CORS_ORIGINS` | **sim** | `https://seu-app.vercel.app` (domínio do front) |
| `DATABASE_URL` | não | `sqlite:////data/sprint_aban.db` (volume) — default é arquivo local |
| `AUTH_USERS_FILE` | não | `/data/auth_users.json` (no volume, p/ persistir usuários) |

### Runbook (com volume montado em `/data`)

```bash
# 1) Configure as env vars acima no provedor; monte um volume em /data.
# 2) Após o 1º deploy, rode uma vez (console/shell do provedor):
python seed_auth.py              # cria /data/auth_users.json (TROQUE as senhas!)
python seed_changelog.py         # importa o histórico (app/data/change_log.json)
# 3) No Vercel, defina VITE_API_URL = URL pública do backend e redeploy.
```

### Banco gerenciado (alternativa ao volume)

Aponte `DATABASE_URL` para um SQLite/Postgres hospedado:
- **Turso** (SQLite): `sqlite+libsql://<host>?authToken=...` (requer `sqlalchemy-libsql`)
- **Neon/Postgres**: `postgresql+psycopg://user:pass@host/db` (requer `psycopg`)
