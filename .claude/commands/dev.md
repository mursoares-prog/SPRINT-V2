# /dev — Sobe os servidores de desenvolvimento

Inicie o frontend e o backend em paralelo e confirme que ambos respondem.

## Passos

1. Suba o backend (FastAPI + uvicorn) em background a partir de `backend/`:
   ```
   cd /Users/murilo/SPRINT-V2/backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000
   ```
   Use `run_in_background: true`.

2. Suba o frontend (Vite) em background a partir de `abandono-app/`:
   ```
   cd /Users/murilo/SPRINT-V2/abandono-app && npm run dev
   ```
   Use `run_in_background: true`.

3. Aguarde ~3 segundos e confirme saúde de ambos:
   - Backend: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health`
   - Frontend: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173`

4. Reporte ao usuário:
   - URL do frontend: http://localhost:5173
   - URL do backend (docs): http://localhost:8000/docs
   - Status de cada servidor (OK / falhou)
