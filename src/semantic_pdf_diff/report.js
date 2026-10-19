// The report page's script (report.py writes the page): inflate the report's parts, gzipped inside the page, put each
// finding's cards and their crops in place, and show findings a page at a time, filtered by relation, kind and words.
(async () => {
  const root = document.getElementById('report');
  let R;
  try {
    const text = atob(document.getElementById('report-data').textContent);
    const bytes = new Uint8Array(text.length);
    for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
    const inflated = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    R = JSON.parse(await new Response(inflated).text());
  } catch (e) {
    root.innerHTML = '<p class="warning">This browser can’t open the report: it needs DecompressionStream '
      + '(Chrome or Edge 80, Firefox 113, Safari 16.4, or later).</p>';
    return;
  }
  const crops = JSON.parse(document.getElementById('report-crops').textContent);
  const PAGE = 100;

  // cards in their places, then their crops
  const fill = (part) => {
    for (const place of part.querySelectorAll('[data-card]')) {
      place.insertAdjacentHTML('afterend', R.cards[place.dataset.card] || '');
      place.remove();
    }
    for (const img of part.querySelectorAll('img[data-crop]')) {
      img.src = 'data:' + crops.type + ';base64,' + crops.data[Number(img.dataset.crop)];
      img.removeAttribute('data-crop');
    }
  };

  // items' HTML shown in box a page at a time, a button showing the next
  const paged = (box, items) => {
    box.textContent = '';
    const more = document.createElement('button');
    more.className = 'more';
    box.append(more);
    let shown = 0;
    const next = () => {
      const part = document.createElement('template');
      part.innerHTML = items.slice(shown, shown + PAGE).join('');
      fill(part.content);
      box.insertBefore(part.content, more);
      shown = Math.min(items.length, shown + PAGE);
      more.hidden = shown >= items.length;
      more.textContent = `Show ${Math.min(PAGE, items.length - shown)} more (${items.length - shown} left)`;
    };
    more.onclick = next;
    next();
  };

  // a finding's words, its cards' included, for the search (worked out once, when first searched)
  const entities = {amp: '&', lt: '<', gt: '>', quot: '"', '#x27': "'"};
  const plain = (html) => html.replace(/<[^>]*>/g, ' ').replace(/&(amp|lt|gt|quot|#x27);/g, (m, e) => entities[e]);
  const words = new Map();
  const wordsOf = (f) => {
    if (!words.has(f)) words.set(f, plain(f.html + ' ' + f.cards.map((id) => R.cards[id] || '').join(' ')).toLowerCase());
    return words.get(f);
  };

  root.innerHTML = R.page;
  const main = root.querySelector('main');
  const relation = root.querySelector('#filter'), kind = root.querySelector('#kind'), query = root.querySelector('#query');
  const show = () => {
    const r = relation.value, k = kind ? kind.value : 'all', q = query.value.toLowerCase().trim();
    const chosen = R.findings.filter((f) => (r === 'all' || f.relation === r) && (k === 'all' || f.kind === k)
      && (!q || wordsOf(f).includes(q)));
    root.querySelector('#count').textContent = `${chosen.length} of ${R.findings.length} findings`;
    paged(main, chosen.map((f) => f.html));
  };
  let typing;
  relation.onchange = show;
  if (kind) kind.onchange = show;
  query.oninput = () => { clearTimeout(typing); typing = setTimeout(show, 200); };
  for (const fold of root.querySelectorAll('details[data-list]')) {
    fold.addEventListener('toggle', () => {
      if (!fold.open || fold.querySelector('.listed')) return;
      const box = document.createElement('div');
      box.className = 'listed';
      fold.append(box);
      paged(box, R.lists[fold.dataset.list]);
    });
  }
  root.addEventListener('click', (e) => {
    if (e.target.matches('img.crop')) e.target.classList.toggle('full');
  });
  show();
})();
