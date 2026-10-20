// The report page's script (report.py writes the page): inflate the report's parts, gzipped inside the page, and show
// them in two views, a page at a time: the findings (filtered by relation, kind, file, topic and words) and every
// claim (by side, how it fared, kind, file, topic and words), each card put in place with its crop. #claims opens on
// the claims.
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

  // cards in their places, then what their claims say (written once however many say it), then their crops
  const fill = (part) => {
    for (const name of ['card', 'said']) {
      const table = name === 'card' ? R.cards : R.said;
      for (const place of part.querySelectorAll(`[data-${name}]`)) {
        place.insertAdjacentHTML('afterend', table[place.dataset[name]] || '');
        place.remove();
      }
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

  // an item's words, its cards' included, for the search (worked out once, when first searched)
  const entities = {amp: '&', lt: '<', gt: '>', quot: '"', '#x27': "'"};
  const plain = (html) => html.replace(/<[^>]*>/g, ' ').replace(/&(amp|lt|gt|quot|#x27);/g, (m, e) => entities[e]);
  const said = (html) => html.replace(/<div data-said="(\d+)"><\/div>/g, (m, n) => R.said[Number(n)]);
  const words = new Map();
  const wordsOf = (x) => {
    if (!words.has(x)) {
      const cards = (x.cards || [x.card]).map((id) => said(R.cards[id] || '')).join(' ');
      words.set(x, plain(x.html + ' ' + cards).toLowerCase());
    }
    return words.get(x);
  };

  root.innerHTML = R.page;
  const main = root.querySelector('main');
  const $ = (id) => root.querySelector('#' + id);
  const relation = $('filter'), kind = $('kind'), same = $('same'), query = $('query');
  const side = $('side'), status = $('status'), claimKind = $('claimkind');
  const file = $('file');  // with more than one pair of files: their indexes, "3,4"
  let view = location.hash === '#claims' ? 'claims' : 'findings';
  let topic = null;  // a topic's index (-1: claims in no topic), or every one
  const inTopic = (x, t) => (t === -1 ? x.topics.every((y) => y === -1) : x.topics.includes(t));
  const chips = [...root.querySelectorAll('.topics button')];
  const show = () => {
    for (const tab of root.querySelectorAll('.views button')) tab.classList.toggle('on', tab.dataset.view === view);
    for (const part of root.querySelectorAll('[data-for]')) part.hidden = part.dataset.for !== view;
    const q = query.value.toLowerCase().trim();
    const files = !file || file.value === 'all' ? null : new Set(file.value.split(',').map(Number));
    const common = (x) => (!files || x.files.some((f) => files.has(f))) && (!q || wordsOf(x).includes(q));
    let matching, folded = 0;
    if (view === 'findings') {
      const r = relation.value, k = kind ? kind.value : 'all';
      const all = R.findings.filter((f) => (r === 'all' || f.relation === r) && (k === 'all' || f.kind === k)
        && common(f));
      matching = same && same.checked ? all.filter((f) => !f.same) : all;
      folded = all.length - matching.length;
    } else {
      const s = side.value, st = status.value, k = claimKind.value;
      matching = R.claims.filter((c) => (s === 'all' || c.side === Number(s)) && (st === 'all' || c.status === st)
        && (k === 'all' || c.kind === k) && common(c));
    }
    for (const chip of chips) {  // each topic's items among those the other filters leave
      const t = Number(chip.dataset.topic);
      chip.querySelector('small').textContent = matching.filter((x) => inTopic(x, t)).length;
      chip.classList.toggle('on', t === topic);
    }
    const chosen = topic === null ? matching : matching.filter((x) => inTopic(x, topic));
    const total = view === 'findings' ? R.findings.length : R.claims.length;
    $('count').textContent = `${chosen.length} of ${total} ${view}`
      + (folded ? ` (${folded} that say the same in both folded)` : '');
    paged(main, chosen.map((x) => x.html));
  };
  let typing;
  for (const control of [relation, kind, same, side, status, claimKind, file]) if (control) control.onchange = show;
  query.oninput = () => { clearTimeout(typing); typing = setTimeout(show, 200); };
  root.addEventListener('click', (e) => {
    if (e.target.matches('img.crop')) e.target.classList.toggle('full');
    const tab = e.target.closest('.views button');
    if (tab) {
      view = tab.dataset.view;
      show();
    }
    const chip = e.target.closest('.topics button');
    if (chip) {  // a topic, or every one again
      topic = topic === Number(chip.dataset.topic) ? null : Number(chip.dataset.topic);
      show();
    }
    if (e.target.matches('button.pick-topic')) {  // a topic's claims, from the coverage table
      view = 'claims';
      topic = Number(e.target.dataset.topic);
      show();
      relation.scrollIntoView();
    }
    if (e.target.matches('button.pick') && file) {  // a file pair's row: its items
      file.value = e.target.dataset.files;
      show();
      relation.scrollIntoView();
    }
  });
  show();
})();
