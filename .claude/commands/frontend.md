# /frontend — Agente de Frontend (React + TypeScript + Vite)

Você é um especialista no frontend deste projeto. Assuma o contexto abaixo antes de agir.

## Estrutura

```
abandono-app/src/
  App.tsx                — roteamento de views (tabs: Admin, FineTuning, Schedule, Logic)
  context/
    AppContext.tsx        — estado global via useReducer; dispatch de todas as ações
  types/                 — tipos TypeScript compartilhados (WizardInputs, ScheduleItem, etc.)
  components/
    Sidebar.tsx          — navegação lateral
    AdminView.tsx        — inputs do wizard (WizardInputs)
    FineTuningView.tsx   — ajuste fino de linhas (FineTuningItem)
    ScheduleView.tsx     — cronograma gerado
    LogicEditorPanel.tsx — editor de lógica customizada
    LogicFlowEditor.tsx  — editor visual ReactFlow (nós: process/decision/start/end)
    LogicQuestionsPanel.tsx — perguntas condicionais por pacote
    InputSummaryPanel.tsx   — resumo dos inputs selecionados
    PackageListPanel.tsx    — lista/seleção de pacotes
    CloudSaveButton.tsx     — salvar/carregar projeto do servidor
    AdminVarsEditor.tsx     — editor de variáveis administrativas
  engines/               — lógica de negócio TS (sequenceEngine, logicEngine, placeholders, etc.)
  data/                  — stores de dados (packages, packageLines, lineDetails, logicSecs)
```

## Convenções

- Tailwind CSS v4 (sem `tailwind.config`; classes diretas)
- Ícones: `lucide-react` e `react-icons`
- Estado global via `AppContext` — use `dispatch` para mutações, nunca estado local para dados compartilhados
- Componentes novos em `src/components/`; sem default exports — use named exports
- Checar tipos: `cd abandono-app && npx tsc -p tsconfig.app.json --noEmit`

## Paleta de cores (dark theme)

```
bg: #0F1923 | surface: #162030 | border: #1E3248
accent: #00A8FF | green: #00C48C | amber: #F0A500 | red: #E05252
text: #D4E4F4 | textMuted: #6B8BAD
```

## Tarefa

$ARGUMENTS

Leia os arquivos relevantes antes de editar. Rode `/types` ao final para confirmar que não há erros.
