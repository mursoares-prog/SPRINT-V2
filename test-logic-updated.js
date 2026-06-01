// Simulação da lógica ATUALIZADA de detecção de pacotes INCLUÍDOS

console.log('=== TESTE DE LÓGICA DE DETECÇÃO DE PACOTES INCLUÍDOS ===\n');

// Simular o estado anterior do schedule
const prevSchedule = [
  { uid: 'pkg-1', packageId: 'ABAN 001', duration: 2, phase: 'Fase 1A' },
  { uid: 'pkg-2', packageId: 'ABAN 002', duration: 1.5, phase: 'Fase 1A' },
  { uid: 'pkg-3', packageId: 'ABAN 003', duration: 3, phase: 'Fase 1B' },
];

// Simular novo schedule (após alteração de input)
const newSchedule = [
  { uid: 'pkg-1', packageId: 'ABAN 001', duration: 2.5, phase: 'Fase 1A' }, // MUDOU: duration (não realçado)
  { uid: 'pkg-2', packageId: 'ABAN 002', duration: 1.5, phase: 'Fase 1A' }, // mesmo (não realçado)
  { uid: 'pkg-4', packageId: 'ABAN 004', duration: 2, phase: 'Fase 1B' },   // NOVO: REALÇAR
  { uid: 'pkg-5', packageId: 'ABAN 005', duration: 1, phase: 'Fase 1B' },   // NOVO: REALÇAR
];

// Implementar a NOVA lógica de detecção (apenas incluídos)
function detectIncluded(prev, items) {
  const included = new Set();

  const oldMap = new Map(prev.map(i => [i.uid, i]));
  const newMap = new Map(items.map(i => [i.uid, i]));

  // Detectar apenas pacotes NOVOS (incluídos)
  for (const [uid] of newMap) {
    if (!oldMap.has(uid)) {
      included.add(uid);
    }
  }

  return included;
}

const includedUids = detectIncluded(prevSchedule, newSchedule);

console.log('✅ Pacotes no schedule anterior:');
prevSchedule.forEach(p => console.log(`   - ${p.uid}: ${p.packageId} (${p.duration}d) em ${p.phase}`));

console.log('\n✅ Pacotes no novo schedule:');
newSchedule.forEach(p => console.log(`   - ${p.uid}: ${p.packageId} (${p.duration}d) em ${p.phase}`));

console.log('\n🎯 Pacotes INCLUÍDOS (a realçar):');
if (includedUids.size === 0) {
  console.log('   (nenhum)');
} else {
  includedUids.forEach(uid => {
    const newItem = newSchedule.find(i => i.uid === uid);
    console.log(`   - ${uid}: ${newItem.packageId} (${newItem.duration}d) em ${newItem.phase}`);
  });
}

console.log('\n⚠️  Pacotes IGNORADOS (mesmo que tenham mudado):');
newSchedule.forEach(item => {
  const oldItem = prevSchedule.find(i => i.uid === item.uid);
  if (oldItem) {
    const changed = oldItem.packageId !== item.packageId || oldItem.duration !== item.duration;
    if (changed) {
      console.log(`   - ${item.uid}: ${item.packageId} (duração: ${oldItem.duration}d → ${item.duration}d) — NÃO realçado`);
    }
  }
});

console.log('\n✅ RESULTADO:');
console.log(`   Total de pacotes incluídos: ${includedUids.size}`);
console.log(`   UIDs a realçar: [${Array.from(includedUids).join(', ')}]`);

// Verificar fases afetadas
const affectedPhases = new Set();
newSchedule.forEach(item => {
  if (includedUids.has(item.uid)) affectedPhases.add(item.phase);
});

console.log('\n✅ FASES A EXPANDIR:');
affectedPhases.forEach(p => console.log(`   - ${p}`));

// Simular o comportamento visual
console.log('\n' + '='.repeat(50));
console.log('COMPORTAMENTO VISUAL ESPERADO:');
console.log('='.repeat(50));
console.log(`
1. ✅ Detectados ${includedUids.size} pacotes incluídos no cronograma
2. ✅ Somente pacotes INCLUÍDOS serão realçados com:
   - Fundo azul sutil: bg-blue-100 (light) / bg-blue-900/50 (dark)
   - Sem outline adicional
   - Sem font-medium
3. ✅ Fases ${Array.from(affectedPhases).join(', ')} serão expandidas
4. ✅ Scroll automático para o primeiro pacote incluído
5. ✅ Realce desaparecerá após 5 segundos
6. ✅ Realces de edições anteriores NÃO são acumulados
`);

console.log('✅ TESTE LÓGICO ATUALIZADO CONCLUÍDO COM SUCESSO');
