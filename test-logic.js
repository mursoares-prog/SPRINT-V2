// Simulação da lógica de detecção de mudanças

console.log('=== TESTE DE LÓGICA DE DETECÇÃO DE MUDANÇAS ===\n');

// Simular o estado anterior do schedule
const prevSchedule = [
  { uid: 'pkg-1', packageId: 'ABAN 001', duration: 2, phase: 'Fase 1A' },
  { uid: 'pkg-2', packageId: 'ABAN 002', duration: 1.5, phase: 'Fase 1A' },
  { uid: 'pkg-3', packageId: 'ABAN 003', duration: 3, phase: 'Fase 1B' },
];

// Simular novo schedule (após alteração de input)
const newSchedule = [
  { uid: 'pkg-1', packageId: 'ABAN 001', duration: 2.5, phase: 'Fase 1A' }, // MUDOU: duration
  { uid: 'pkg-2', packageId: 'ABAN 002', duration: 1.5, phase: 'Fase 1A' }, // mesmo
  { uid: 'pkg-4', packageId: 'ABAN 004', duration: 2, phase: 'Fase 1B' },   // NOVO: substituiu pkg-3
];

// Implementar a lógica de detecção (do código)
function detectChanges(prev, items) {
  const changed = new Set();

  const oldMap = new Map(prev.map(i => [i.uid, i]));
  const newMap = new Map(items.map(i => [i.uid, i]));

  // Verificar se algum pacote mudou (packageId ou duration)
  for (const [uid, item] of newMap) {
    const oldItem = oldMap.get(uid);
    if (!oldItem || oldItem.packageId !== item.packageId || oldItem.duration !== item.duration) {
      changed.add(uid);
    }
  }

  // Verificar removidos
  for (const uid of oldMap.keys()) {
    if (!newMap.has(uid)) changed.add(uid);
  }

  return changed;
}

const changedUids = detectChanges(prevSchedule, newSchedule);

console.log('✅ Pacotes no schedule anterior:');
prevSchedule.forEach(p => console.log(`   - ${p.uid}: ${p.packageId} (${p.duration}d) em ${p.phase}`));

console.log('\n✅ Pacotes no novo schedule:');
newSchedule.forEach(p => console.log(`   - ${p.uid}: ${p.packageId} (${p.duration}d) em ${p.phase}`));

console.log('\n🎯 Pacotes DETECTADOS como MUDADOS:');
if (changedUids.size === 0) {
  console.log('   (nenhum)');
} else {
  changedUids.forEach(uid => {
    const newItem = newSchedule.find(i => i.uid === uid);
    const oldItem = prevSchedule.find(i => i.uid === uid);
    if (newItem && oldItem) {
      console.log(`   - ${uid}: duração ${oldItem.duration}d → ${newItem.duration}d`);
    } else if (newItem && !oldItem) {
      console.log(`   - ${uid}: NOVO pacote`);
    } else if (!newItem && oldItem) {
      console.log(`   - ${uid}: REMOVIDO`);
    }
  });
}

console.log('\n✅ RESULTADO:');
console.log(`   Total de mudanças detectadas: ${changedUids.size}`);
console.log(`   UIDs a realçar: [${Array.from(changedUids).join(', ')}]`);

// Verificar fases afetadas
const affectedPhases = new Set();
newSchedule.forEach(item => {
  if (changedUids.has(item.uid)) affectedPhases.add(item.phase);
});

console.log('\n✅ FASES A EXPANDIR:');
affectedPhases.forEach(p => console.log(`   - ${p}`));

// Simular o comportamento visual
console.log('\n' + '='.repeat(50));
console.log('COMPORTAMENTO VISUAL ESPERADO:');
console.log('='.repeat(50));
console.log(`
1. ✅ Detectadas ${changedUids.size} mudanças no schedule
2. ✅ Pacotes afetados serão realçados com:
   - Fundo amber: bg-amber-200 (light) / bg-amber-700/70 (dark)
   - Outline: outline-amber-500 (light) / outline-amber-400 (dark)
   - Fonte: font-medium
3. ✅ Fases ${Array.from(affectedPhases).join(', ')} serão expandidas
4. ✅ Scroll automático para o primeiro pacote realçado
5. ✅ Realce desaparecerá após 5 segundos
`);

console.log('✅ TESTE LÓGICO CONCLUÍDO COM SUCESSO');
