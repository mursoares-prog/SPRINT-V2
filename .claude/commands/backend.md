# /backend — Agente de Backend (FastAPI + SQLAlchemy)

Você é um especialista no backend deste projeto. Assuma o contexto abaixo antes de agir.

## Estrutura

```
backend/
  app/
    main.py          — FastAPI app, CORS, migrações idempotentes
    models.py        — Modelos SQLAlchemy (mapped_column, Base)
    schemas.py       — Schemas Pydantic de entrada/saída
    database.py      — engine, SessionLocal, Base
    auth.py          — autenticação JWT
    routers/
      projects.py    — CRUD de projetos (ProjectIn / ProjectSummary)
      engines.py     — endpoints de cálculo (sequence, placeholders, logic)
      logic.py       — lógica customizada por projeto
      base.py        — dados base (packages, sequences)
      changelog.py   — changelog de linhas
      auth.py        — login/logout
    engines/
      sequence_engine.py  — port Python do sequenceEngine.ts (paridade garantida por testes)
      placeholders.py     — substituição de tokens em textos de linha
      nipple_depth.py     — cálculo de profundidade de nipple
    data/            — JSONs exportados pelo TS (packages, sequences, etc.)
  tests/             — pytest; fixtures em genSequenceFixtures.ts / genPlaceholderFixtures.ts
  .venv/             — virtualenv; executável: .venv/bin/python
```

## Convenções

- Novos endpoints entram num router existente ou num novo arquivo em `routers/`; registrar em `main.py`
- Schemas Pydantic em `schemas.py`; modelos SQLAlchemy em `models.py`
- Migrações simples via `_migrate_*` em `main.py` (ADD COLUMN idempotente); para mudanças maiores, Alembic
- Rodar testes: `cd backend && .venv/bin/python -m pytest -q`
- O `sequence_engine.py` Python deve manter paridade com o TS — ao alterar um, alterar o outro

## Tarefa

$ARGUMENTS

Leia os arquivos relevantes antes de editar. Rode os testes ao final.
