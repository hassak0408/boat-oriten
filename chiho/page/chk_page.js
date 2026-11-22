// ページの確かめ：node chk_page.js ページ.html（スマホ2つとPCで、エラー・横はみ出し・印の数・1着と3着内の割り振りの合計）
const { chromium, devices } = require('playwright');
(async () => {
  const b = await chromium.launch();
  for (const [nm, opt] of [['se', devices['iPhone SE']], ['iphone13', devices['iPhone 13']], ['pc', { viewport: { width: 1024, height: 800 } }]]) {
    const ctx = await b.newContext(opt); const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', e => errs.push(String(e)));
    await p.goto('file://' + process.argv[2]); await p.waitForTimeout(600);
    const r = await p.evaluate(() => {
      const races = [...document.querySelectorAll('#list .race')]; let bad = 0;
      races.forEach(c => { for (const col of [2, 4]) { const v = [...c.querySelectorAll('.hr:not(.hd) .p1')].filter((x, i) => i % 3 === (col === 2 ? 0 : 2)).map(x => parseInt(x.textContent)); if (v.length && !v.some(isNaN) && v.reduce((a, b) => a + b, 0) !== 100) bad++; } });
      return { sw: document.documentElement.scrollWidth, race: races.length, ace: document.querySelectorAll('.hr.ace').length, cut: document.querySelectorAll('.cutline').length,
               rec: document.querySelectorAll('.rec').length, ov: document.querySelectorAll('#ovl button').length, memo: document.querySelectorAll('.memo').length, bad, title: document.title };
    });
    console.log(nm, JSON.stringify(r), 'err', errs.join(' ') || 'なし');
    await ctx.close();
  }
  await b.close();
})();
