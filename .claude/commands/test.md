# /test — Roda todos os testes do projeto

Execute testes do backend (pytest) e verificação de tipos do frontend (tsc), reporte falhas.

## Passos

1. Rode os testes Python a partir de `backend/`:
   ```
   cd /Users/murilo/SPRINT-V2/backend && .venv/bin/python -m pytest -q 2>&1
   ```

2. Rode a verificação de tipos TypeScript a partir de `abandono-app/`:
   ```
   cd /Users/murilo/SPRINT-V2/abandono-app && npx tsc -p tsconfig.app.json --noEmit 2>&1
   ```

3. Rode o linter ESLint:
   ```
   cd /Users/murilo/SPRINT-V2/abandono-app && npm run lint 2>&1
   ```

4. Consolide e reporte:
   - Pytest: X passed, Y failed — liste os nomes dos testes que falharam
   - TypeScript: OK ou liste os erros com arquivo:linha
   - ESLint: OK ou liste os warnings/erros
   - Se tudo passou, diga "Todos os checks passaram ✓"
