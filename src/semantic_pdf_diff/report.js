// The report page's script (report.py writes the page): inflate the report's parts, gzipped inside the page, put each
// finding's cards and their crops in place, and show findings a page at a time, filtered by relation, kind, file and
// words.
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

  // a finding's words, its cards' included, for the search (worked out once, when first searched)
  const entities = {amp: '&', lt: '<', gt: '>', quot: '"', '#x27': "'"};
  const plain = (html) => html.replace(/<[^>]*>/g, ' ').replace(/&(amp|lt|gt|quot|#x27);/g, (m, e) => entities[e]);
  const said = (html) => html.replace(/<div data-said="(\d+)"><\/div>/g, (m, n) => R.said[Number(n)]);
  const words = new Map();
  const wordsOf = (f) => {
    if (!words.has(f)) {
      words.set(f, plain(f.html + ' ' + f.cards.map((id) => said(R.cards[id] || '')).join(' ')).toLowerCase());
    }
    return words.get(f);
  };

  root.innerHTML = R.page;
  const main = root.querySelector('main');
  const relation = root.querySelector('#filter'), kind = root.querySelector('#kind');
  const query = root.querySelector('#query');
  const file = root.querySelector('#file');  // with more than one pair of files: their indexes, "3,4"
  const same = root.querySelector('#same');  // folding the equivalent findings whose claims say the same
  let topic = null;  // a topic's index (-1: claims in no topic), or every finding
  const inTopic = (f, t) => (t === -1 ? f.topics.every((x) => x === -1) : f.topics.includes(t));
  const chips = [...root.querySelectorAll('.topics button')];
  const show = () => {
    const r = relation.value, k = kind ? kind.value : 'all', q = query.value.toLowerCase().trim();
    const files = !file || file.value === 'all' ? null : new Set(file.value.split(',').map(Number));
    const matching = R.findings.filter((f) => (r === 'all' || f.relation === r) && (k === 'all' || f.kind === k)
      && (!files || files.has(f.files[0]) || files.has(f.files[1])) && (!q || wordsOf(f).includes(q)));
    const unfolded = same && same.checked ? matching.filter((f) => !f.same) : matching;
    for (const chip of chips) {  // each topic's findings among those the other filters leave
      const t = Number(chip.dataset.topic);
      chip.querySelector('small').textContent = unfolded.filter((f) => inTopic(f, t)).length;
      chip.classList.toggle('on', t === topic);
    }
    const chosen = topic === null ? unfolded : unfolded.filter((f) => inTopic(f, topic));
    const folded = matching.length - unfolded.length;
    root.querySelector('#count').textContent = `${chosen.length} of ${R.findings.length} findings`
      + (folded ? ` (${folded} that say the same in both folded)` : '');
    paged(main, chosen.map((f) => f.html));
  };
  let typing;
  relation.onchange = show;
  if (kind) kind.onchange = show;
  if (file) file.onchange = show;
  if (same) same.onchange = show;
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
    const chip = e.target.closest('.topics button');
    if (chip) {  // a topic, or every finding again
      topic = topic === Number(chip.dataset.topic) ? null : Number(chip.dataset.topic);
      show();
    }
    if (e.target.matches('button.pick') && file) {  // a file pair's row: its findings
      file.value = e.target.dataset.files;
      show();
      relation.scrollIntoView();
    }
  });
  show();
})();
