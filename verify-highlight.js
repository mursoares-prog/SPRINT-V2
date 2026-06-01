const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();

  try {
    // Navegar para a aplicação
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

    console.log('✅ App carregado');

    // Esperar aparecer o botão de começar
    await page.waitForSelector('button:has-text("Começar")', { timeout: 5000 });
    console.log('✅ Tela inicial carregada');

    // Clicar no botão Começar
    await page.click('button:has-text("Começar")');

    // Esperar o wizard aparecer
    await page.waitForSelector('input[placeholder*="poço"]', { timeout: 5000 });
    console.log('✅ Wizard iniciado');

    // Preencher nome do poço
    await page.fill('input[placeholder*="poço"]', 'Poço Teste');

    // Avançar etapas até chegar na etapa 2 (ScheduleView)
    // Buscar o botão próximo
    let attempts = 0;
    while (attempts < 20) {
      const nextBtn = await page.$('button:has-text("Próximo")');
      if (!nextBtn) break;

      await nextBtn.click();
      await page.waitForTimeout(500);

      // Verificar se chegou na etapa 2 (ScheduleView com tabela de cronograma)
      const hasSchedule = await page.$('table');
      if (hasSchedule) {
        console.log('✅ Chegou na etapa 2 (ScheduleView)');
        break;
      }
      attempts++;
    }

    // Tirar screenshot antes de fazer mudança
    await page.screenshot({ path: 'before-change.png' });
    console.log('📸 Screenshot antes: before-change.png');

    // Encontrar o painel de inputs (InputSummaryPanel)
    // Procurar por algum input que modifique o schedule
    const inputPanel = await page.$('[class*="InputSummaryPanel"]');
    if (inputPanel) {
      console.log('✅ InputSummaryPanel encontrado');
    }

    // Procurar por inputs/selects que possam ser alterados
    const selects = await page.$$('select');
    if (selects.length > 0) {
      console.log(`✅ Encontrados ${selects.length} selects`);

      // Alterar o primeiro select
      const firstSelect = selects[0];
      const options = await firstSelect.$$eval('option', opts => opts.map(o => o.value).filter(v => v));

      if (options.length > 1) {
        const currentValue = await firstSelect.inputValue();
        const newValue = options.find(o => o !== currentValue) || options[0];

        console.log(`📝 Alterando select de "${currentValue}" para "${newValue}"`);

        // Alterar valor
        await firstSelect.selectOption(newValue);
        await page.waitForTimeout(500);

        // Procurar por elementos com realce (amber-200)
        const highlightedRows = await page.$$('[style*="amber"], [class*="bg-amber"]');
        console.log(`🎯 Elementos com realce amber encontrados: ${highlightedRows.length}`);

        // Tirar screenshot após mudança
        await page.screenshot({ path: 'after-change.png' });
        console.log('📸 Screenshot depois: after-change.png');

        // Esperar para ver se o realce desaparece após 5 segundos
        console.log('⏱️  Aguardando 5 segundos para verificar se realce desaparece...');
        await page.waitForTimeout(5500);

        const highlightedRowsAfter = await page.$$('[style*="amber"], [class*="bg-amber"]');
        console.log(`🎯 Elementos com realce amber após 5s: ${highlightedRowsAfter.length}`);

        // Tirar screenshot final
        await page.screenshot({ path: 'after-highlight-fade.png' });
        console.log('📸 Screenshot final: after-highlight-fade.png');

        console.log('\n✅ TESTE CONCLUÍDO COM SUCESSO');
      }
    } else {
      console.log('❌ Nenhum select encontrado');
    }

  } catch (error) {
    console.error('❌ Erro durante teste:', error.message);
  } finally {
    await browser.close();
  }
})();
