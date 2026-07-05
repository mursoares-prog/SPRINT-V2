# /feature — Agente de Feature Full-Stack

Implemente uma feature completa (backend + frontend + teste) a partir de uma descrição.

## Processo

### 1. Planejamento (faça antes de qualquer edição)
- Entenda o requisito em $ARGUMENTS
- Identifique quais arquivos precisam mudar (backend/frontend/engine/ambos)
- Liste as alterações planejadas e confirme com o usuário se houver ambiguidade

### 2. Backend (se necessário)
Contexto em `/backend`. Tipicamente:
- Novo schema em `backend/app/schemas.py`
- Nova lógica em router ou engine
- Migração idempotente em `main.py` se houver nova coluna

### 3. Frontend (se necessário)
Contexto em `/frontend`. Tipicamente:
- Novo tipo em `src/types/`
- Novo componente em `src/components/` ou alteração de existente
- Novo action no reducer de `AppContext.tsx`
- Chamada à API via fetch

### 4. Testes
- Se mudou lógica de engine: regenere fixtures e rode `pytest tests/test_*engine*.py`
- Se mudou endpoint: adicione/atualize teste em `backend/tests/`
- Se mudou tipo TS: rode `cd abandono-app && npx tsc -p tsconfig.app.json --noEmit`

### 5. Checklist de entrega
- [ ] TypeScript sem erros (`/types`)
- [ ] Testes passando (`/test`)
- [ ] Feature funciona no fluxo principal

## Tarefa

$ARGUMENTS
