# /engine — Agente de Logic/Sequence Engine

Você é especialista nos motores de cálculo deste projeto (TS e Python). Assuma o contexto abaixo.

## Motores

### sequenceEngine (TS + Python espelho)
- **TS**: `abandono-app/src/engines/sequenceEngine.ts` — `generateSchedule(inputs)` → `ScheduleItem[]`
- **Python**: `backend/app/engines/sequence_engine.py` — port fiel do TS
- **Paridade garantida por**: `backend/tests/test_sequence_engine.py` contra golden gerado por `abandono-app/scripts/genSequenceFixtures.ts`
- **Dados**: `backend/app/data/{packages,sequences,package_durations}.json` (exportados pelo TS via `scripts/dumpEngineData.ts`)

### logicEngine (TS only)
- `abandono-app/src/engines/logicEngine.ts`
- Executa lógica customizada (seções `LSec`, decisões `LDec`, pacotes `LPkg`) sobre `WizardInputs`
- Condições em `checkCondition()` — lista exaustiva de `LCondition`

### placeholders (TS + Python espelho)
- **TS**: `abandono-app/src/engines/placeholders.ts` — `applyPlaceholders(line, inputs)`
- **Python**: `backend/app/engines/placeholders.py`
- Substitui tokens `{NOME}` em textos de linha com dados derivados dos inputs

### nippleDepth
- `abandono-app/src/engines/nippleDepth.ts` / `backend/app/engines/nipple_depth.py`
- Cálculo de profundidade de nipple BHA

## Regra crítica de paridade

Ao alterar qualquer motor TS, altere o espelho Python e vice-versa.
Após a mudança:
1. Regenere os fixtures: `cd abandono-app && npx --yes tsx scripts/genSequenceFixtures.ts`
2. Rode os testes: `cd backend && .venv/bin/python -m pytest tests/test_sequence_engine.py -q`

## Tarefa

$ARGUMENTS

Leia os arquivos relevantes (TS e Python) antes de editar. Garanta paridade e rode os testes.
