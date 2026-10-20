// The report page's script (report.py writes the page; search.js finds what's searched): inflate the report's parts,
// gzipped inside the page, and show them in two views, a page at a time: the findings (filtered by relation, kind,
// file, topic and a search) and every claim (by side, how it fared, kind, file, topic and a search), each card put in
// place with its crop. The view and the search are kept in the page's address: #claims&q=feed%20pump.
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

  // cards in their places, each with a search for the claims like it, then what their claims say (written once
  // however many say it), then their crops
  const fill = (part) => {
    for (const name of ['card', 'said']) {
      const table = name === 'card' ? R.cards : R.said;
      for (const place of part.querySelectorAll(`[data-${name}]`)) {
        place.insertAdjacentHTML('afterend', table[place.dataset[name]] || '');
        const small = name === 'card' && place.nextElementSibling && place.nextElementSibling.querySelector('small');
        if (small) {
          const like = document.createElement('button');
          like.className = 'like';
          like.dataset.like = place.dataset.card;
          like.textContent = 'Claims like this';
          small.append(' · ', like);
        }
        place.remove();
      }
    }
    for (const img of part.querySelectorAll('img[data-crop]')) {
      img.src = 'data:' + crops.type + ';base64,' + crops.data[Number(img.dataset.crop)];
      img.removeAttribute('data-crop');
    }
  };

  // items' HTML shown in box a page at a time, a button showing the next; mark(part) marks what was searched
  const paged = (box, items, mark) => {
    box.textContent = '';
    const more = document.createElement('button');
    more.className = 'more';
    box.append(more);
    let shown = 0;
    const next = () => {
      const part = document.createElement('template');
      part.innerHTML = items.slice(shown, shown + PAGE).join('');
      fill(part.content);
      if (mark) mark(part.content);
      box.insertBefore(part.content, more);
      shown = Math.min(items.length, shown + PAGE);
      more.hidden = shown >= items.length;
      more.textContent = `Show ${Math.min(PAGE, items.length - shown)} more (${items.length - shown} left)`;
    };
    more.onclick = next;
    next();
  };

  root.innerHTML = R.page;
  const main = root.querySelector('main');
  const $ = (id) => root.querySelector('#' + id);
  const relation = $('filter'), kind = $('kind'), same = $('same'), query = $('query');
  const side = $('side'), status = $('status'), claimKind = $('claimkind');
  const order = $('order'), orderBox = $('order-box');
  const paired = $('counterparts'), pairedBox = $('counterparts-box'), also = $('also');
  const file = $('file');  // with more than one pair of files: their indexes, "3,4"
  const sides = [...side.options].filter((o) => o.value !== 'all').map((o) => o.textContent);
  const tabs = [...root.querySelectorAll('.views button')];
  const labels = new Map(tabs.map((tab) => [tab, tab.textContent]));

  // the index of the cards' words, built a slice at a time once the page is shown (a search finishes it)
  const index = Search.index(R);
  const build = () => {
    if (!index.step(12)) setTimeout(build, 0);
  };
  setTimeout(build, 0);

  const address = () => new URLSearchParams(location.hash.slice(1));
  let view = address().has('claims') ? 'claims' : 'findings';
  query.value = address().get('q') || '';
  const remember = () => {  // the view and the search, in the address
    const q = query.value.trim();
    const hash = [view === 'claims' ? 'claims' : '', q ? 'q=' + encodeURIComponent(q) : ''].filter(Boolean).join('&');
    if (location.hash.slice(1) === hash) return;
    try {
      history.replaceState(null, '', hash ? '#' + hash : location.pathname + location.search);
    } catch (e) {  // a browser keeping a file's address as it is: the page still works
    }
  };

  // each claim's counterparts: the claims findings pair it with (pairs judged unrelated aren't findings)
  const counterparts = new Map(), claimOf = new Map(R.claims.map((c) => [c.card, c]));
  for (const f of R.findings) {
    for (const [x, y] of [f.cards, [...f.cards].reverse()]) {
      if (!counterparts.has(x)) counterparts.set(x, []);
      counterparts.get(x).push(y);
    }
  }
  // the found claims' counterparts the search didn't find (each scored half its counterpart's), and the other
  // source's names for what was searched: a counterpart's entity or attribute where the found claim's holds the
  // words searched and the counterpart's doesn't ("rated output" found, "nominal power" its counterpart's)
  const pairedWith = (groups, found) => {
    const added = new Map(), names = new Map();
    for (const [claim, score] of found) {
      const own = index.named(claim.card);
      for (const card of counterparts.get(claim.card) || []) {
        const other = claimOf.get(card);
        if (!other) continue;
        if (!found.has(other)) added.set(other, Math.max(added.get(other) || 0, score / 2));
        index.named(card).forEach((name, i) => {
          if (!name.trim() || !Search.touches(groups, own[i]) || Search.covers(groups, name)) return;
          const key = Search.words(name).join(' ');
          const seen = names.get(key);  // the first spelling found, as search.py keeps it
          names.set(key, {name: seen ? seen.name : name, n: (seen ? seen.n : 0) + 1});
        });
      }
    }
    return {added, names: [...names.values()].sort((a, b) => b.n - a.n).slice(0, 6)};
  };
  const COUNTERPART = '<p class="meta"><b>The counterpart of a claim the search found.</b> ';
  const OTHER_NAME_SHARE = 0.5;  // a claim found by another name scores half (search.py's)
  const esc = (text) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
  const byName = (name) => `<p class="meta"><b>Found by another name the model gave: ${esc(name)}.</b></p>`;

  let topic = null;  // a topic's index (-1: claims in no topic), or every one
  const inTopic = (x, t) => (t === -1 ? x.topics.every((y) => y === -1) : x.topics.includes(t));
  const chips = [...root.querySelectorAll('.topics button')];
  const show = () => {
    for (const tab of tabs) tab.classList.toggle('on', tab.dataset.view === view);
    for (const part of root.querySelectorAll('[data-for]')) part.hidden = part.dataset.for !== view;
    const groups = Search.parse(query.value, index.unitOf);
    const among = groups.length ? index.find(groups) : null;
    const searched = among && {findings: among(R.findings), claims: among(R.claims)};
    const worded = groups.some((g) => !g.not && g.terms.some((t) => t.words));
    const extra = searched && worded ? pairedWith(groups, searched.claims) : {added: new Map(), names: []};
    if (paired.checked) for (const [claim, score] of extra.added) searched.claims.set(claim, score);
    const added = paired.checked ? extra.added : new Map();
    // the model's other names for it (the search_names lever): what they find, after what the query found
    const others = searched ? Search.otherNames(groups, R.synonyms) : [], renamed = new Map();
    for (const other of paired.checked ? others : []) {
      const alike = index.find(other.groups);
      for (const key of ['claims', 'findings']) {
        for (const [x, score] of alike(key === 'claims' ? R.claims : R.findings)) {
          if (searched[key].has(x)) continue;
          searched[key].set(x, score * OTHER_NAME_SHARE);
          renamed.set(x, other.name);
        }
      }
    }
    pairedBox.hidden = !extra.added.size && !others.length;
    also.hidden = !extra.names.length && !others.length;
    also.textContent = '';
    const offer = (title, offered) => {  // names offered as searches: [name, how many claims gave it, or none]
      if (!offered.length) return;
      also.append((also.childNodes.length ? ' · ' : '') + title);
      for (const [name, n] of offered) {
        const button = document.createElement('button');
        button.className = 'also';
        button.dataset.q = `"${name.replace(/"/g, '')}"`;
        button.textContent = name + ' ';
        if (n) button.append(Object.assign(document.createElement('small'), {textContent: n}));
        also.append(button);
      }
    };
    offer('The other source\'s names for it: ', extra.names.map(({name, n}) => [name, n]));
    offer('The model\'s other names for it: ', others.map((o) => [o.name, 0]));
    const found = searched && searched[view];
    for (const tab of tabs) {
      const all = tab.dataset.view === 'findings' ? R.findings : R.claims;
      tab.textContent = searched ? `${labels.get(tab)} (${searched[tab.dataset.view].size} found)` : labels.get(tab);
      if (searched) tab.title = `${searched[tab.dataset.view].size} of ${all.length} found by the search`;
      else tab.removeAttribute('title');
    }
    const files = !file || file.value === 'all' ? null : new Set(file.value.split(',').map(Number));
    const common = (x) => (!files || x.files.some((f) => files.has(f))) && (!found || found.has(x));
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
    let chosen = topic === null ? matching : matching.filter((x) => inTopic(x, topic));
    orderBox.hidden = !found;
    if (found && order.value === 'relevance') chosen = [...chosen].sort((a, b) => found.get(b) - found.get(a));
    const total = view === 'findings' ? R.findings.length : R.claims.length;
    let count = `${chosen.length} of ${total} ${view}`
      + (folded ? ` (${folded} that say the same in both folded)` : '');
    if (found && view === 'claims') {  // what each source says, as searched
      const via = chosen.filter((c) => added.has(c)).length, named = chosen.filter((c) => renamed.has(c)).length;
      const how = [via ? `${via} as counterparts` : '', named ? `${named} by other names` : ''].filter(Boolean);
      count += (how.length ? ` (${how.join(', ')})` : '') + ': '
        + sides.map((name, i) => `${chosen.filter((c) => c.side === i).length} in ${name}`).join('; ');
    }
    const strange = Search.unknown(groups);
    if (strange.length) count += ` · units the search doesn't know: ${strange.join(', ')}`;
    $('count').textContent = count;
    if (found && view === 'findings') {
      const named = chosen.filter((f) => renamed.has(f)).length;
      if (named) count += ` (${named} by other names)`;
    }
    const shown = (x) => {
      if (renamed.has(x)) return x.html.replace(/^<[^>]*>/, (m) => m + byName(renamed.get(x)));  // its first tag
      return view === 'claims' && added.has(x) ? x.html.replace('<p class="meta">', COUNTERPART) : x.html;
    };
    paged(main, chosen.map(shown), found ? Search.marker(groups, index) : null);
    remember();
  };
  let typing;
  for (const control of [relation, kind, same, side, status, claimKind, file, order, paired]) {
    if (control) control.onchange = show;
  }
  query.oninput = () => {
    clearTimeout(typing);
    typing = setTimeout(show, 200);
  };
  window.addEventListener('hashchange', () => {  // an address edited, or another search's
    view = address().has('claims') ? 'claims' : 'findings';
    query.value = address().get('q') || '';
    show();
  });
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
    const name = e.target.closest('button.also');
    if (name) {  // the other source's name for what was searched, searched
      query.value = name.dataset.q;
      show();
    }
    if (e.target.matches('button.like')) {  // the claims like a claim: the other source's, most alike first
      const claim = R.claims.find((c) => c.card === e.target.dataset.like);
      query.value = 'like:' + e.target.dataset.like;
      view = 'claims';
      topic = null;
      if (claim && claim.side >= 0 && sides.length === 2) side.value = String(1 - claim.side);
      order.value = 'relevance';
      show();
      query.scrollIntoView();
    }
  });
  show();
})();
