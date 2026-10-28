// The report page's script (report.py writes the page; search.js finds what's searched): inflate the report's parts,
// gzipped inside the page, and show them in two views, a page at a time: the findings (filtered by relation, kind,
// file, topic and a search) and every claim (by side, how it fared, kind, file, topic and a search), each card put in
// place with its crop. What's shown is kept in the page's address, defaults left out (#claims&side=1&q=feed%20pump),
// and a claim or finding linked (#claims&claim=ID, #finding=A~B) is paged to and marked: an address to bookmark or
// share (docs/plans/report-snippets-and-bookmarks-2026-10-28.md, milestone 2). Changing view, following a link and
// "Claims like this" are steps Back returns from; filtering and typing replace the address.
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

  // items' HTML shown in box a page at a time, a button showing the next; mark(part) marks what was searched; keys:
  // each item's own address (a claim's id, a finding's two), given to its Link button. Returns reach(i): the i-th
  // item's element, the pages up to it shown
  const paged = (box, items, mark, keys) => {
    box.textContent = '';
    const more = document.createElement('button');
    more.className = 'more';
    box.append(more);
    const placed = [];  // each item's element (an item's HTML is one element)
    let shown = 0;
    const next = () => {
      const part = document.createElement('template');
      part.innerHTML = items.slice(shown, shown + PAGE).join('');
      fill(part.content);
      if (mark) mark(part.content);
      for (const item of part.content.children) {
        const link = document.createElement('button');
        link.className = 'link';
        link.dataset.link = keys[placed.length];
        link.textContent = 'Link';
        link.title = 'Its address in the address bar, to bookmark or share';
        const heading = item.querySelector('h2, p.meta');
        if (heading) heading.append(' ', link);
        placed.push(item);
      }
      box.insertBefore(part.content, more);
      shown = Math.min(items.length, shown + PAGE);
      more.hidden = shown >= items.length;
      more.textContent = `Show ${Math.min(PAGE, items.length - shown)} more (${items.length - shown} left)`;
    };
    more.onclick = next;
    next();
    return (i) => {
      while (placed.length <= i && shown < items.length) next();
      return placed[i];
    };
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

  // the address: the view ("claims", else the findings), each control not at its default (a box unticked, "off"),
  // the topic, the search, and the claim or finding linked (target: {kind, id}), in that order
  const address = () => new URLSearchParams(location.hash.slice(1));
  const CONTROLS = [['relation', relation], ['kind', kind], ['side', side], ['status', status], ['read', claimKind],
    ['file', file], ['order', order]].filter(([, c]) => c);
  const BOXES = [['fold', same], ['counterparts', paired]].filter(([, c]) => c);  // ticked unless the address says
  const initial = new Map(CONTROLS.map(([key, c]) => [key, c.value]));
  let view = 'findings', target = null;
  const hashOf = () => {
    const q = query.value.trim(), parts = [view === 'claims' ? 'claims' : ''];
    for (const [key, c] of CONTROLS) {
      if (c.value !== initial.get(key)) parts.push(key + '=' + encodeURIComponent(c.value));
    }
    for (const [key, c] of BOXES) if (!c.checked) parts.push(key + '=off');
    parts.push(topic === null ? '' : 'topic=' + topic, q ? 'q=' + encodeURIComponent(q) : '');
    if (target) parts.push(target.kind + '=' + encodeURIComponent(target.id));
    return parts.filter(Boolean).join('&');
  };
  const remember = (step) => {  // a step Back returns from, or the address replaced
    const hash = hashOf();
    if (location.hash.slice(1) === hash) return;
    try {
      history[step ? 'pushState' : 'replaceState'](null, '', hash ? '#' + hash : location.pathname + location.search);
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
  const keyOf = (x) => (x.cards ? x.cards.join('~') : x.card);  // a finding's address, or a claim's
  let listed = [], reach = () => undefined;  // the items shown, and the way to one of them
  const show = (step) => {
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
    const asked = (key) => groups.some((g) => g.terms.some((t) => t[key] !== undefined));
    if (asked('meaning')) count += ' · meaning: is searched from the command line (semantic-pdf-diff search)';
    if (asked('near') && !index.embedded()) count += ' · near: needs the claims embedded (embed_model)';
    $('count').textContent = count;
    if (found && view === 'findings') {
      const named = chosen.filter((f) => renamed.has(f)).length;
      if (named) count += ` (${named} by other names)`;
    }
    const shown = (x) => {
      if (renamed.has(x)) return x.html.replace(/^<[^>]*>/, (m) => m + byName(renamed.get(x)));  // its first tag
      return view === 'claims' && added.has(x) ? x.html.replace('<p class="meta">', COUNTERPART) : x.html;
    };
    listed = chosen;
    reach = paged(main, chosen.map(shown), found ? Search.marker(groups, index) : null, chosen.map(keyOf));
    remember(step);
  };

  // the claim or finding linked: its page reached, scrolled to and marked; where what the address shows leaves it
  // out, every filter and the search are cleared (and equal findings unfolded) to show it
  const marked = (element) => {
    for (const x of root.querySelectorAll('main .linked')) x.classList.remove('linked');
    if (element) element.classList.add('linked');
  };
  const reveal = () => {
    let at = listed.findIndex((x) => keyOf(x) === target.id);
    if (at < 0) {
      for (const [key, c] of CONTROLS) c.value = initial.get(key);
      if (same) same.checked = false;
      topic = null;
      query.value = '';
      show();
      at = listed.findIndex((x) => keyOf(x) === target.id);
    }
    if (at < 0) {
      $('count').textContent += ` · the ${target.kind} linked isn't in this report`;
      return;
    }
    const element = reach(at);
    marked(element);
    element.scrollIntoView({block: 'start'});
  };
  // what the address shows: on opening, on Back and Forward, and when it's edited
  const restore = () => {
    const a = address();
    target = a.has('finding') ? {kind: 'finding', id: a.get('finding')}
      : a.has('claim') ? {kind: 'claim', id: a.get('claim')} : null;
    view = target ? (target.kind === 'claim' ? 'claims' : 'findings') : a.has('claims') ? 'claims' : 'findings';
    for (const [key, c] of CONTROLS) {
      c.value = a.has(key) ? a.get(key) : initial.get(key);
      if (c.selectedIndex < 0) c.value = initial.get(key);  // an option this report hasn't
    }
    for (const [key, c] of BOXES) c.checked = a.get(key) !== 'off';
    const t = a.has('topic') ? Number(a.get('topic')) : null;
    topic = chips.some((chip) => Number(chip.dataset.topic) === t) ? t : null;
    query.value = a.get('q') || '';
    show();
    if (target) reveal();
  };

  const changed = () => {  // a filter changed: the address replaced, without the item linked
    target = null;
    show();
  };
  let typing;
  for (const control of [relation, kind, same, side, status, claimKind, file, order, paired]) {
    if (control) control.onchange = changed;
  }
  query.oninput = () => {
    clearTimeout(typing);
    typing = setTimeout(changed, 200);
  };
  window.addEventListener('hashchange', restore);
  root.addEventListener('click', (e) => {
    if (e.target.matches('img.crop')) e.target.classList.toggle('full');
    const tab = e.target.closest('.views button');
    if (tab) {
      view = tab.dataset.view;
      target = null;
      show(true);
    }
    const chip = e.target.closest('.topics button');
    if (chip) {  // a topic, or every one again
      topic = topic === Number(chip.dataset.topic) ? null : Number(chip.dataset.topic);
      changed();
    }
    if (e.target.matches('button.pick-topic')) {  // a topic's claims, from the coverage table
      view = 'claims';
      topic = Number(e.target.dataset.topic);
      target = null;
      show(true);
      relation.scrollIntoView();
    }
    if (e.target.matches('button.pick') && file) {  // a file pair's row: its items
      file.value = e.target.dataset.files;
      changed();
      relation.scrollIntoView();
    }
    const name = e.target.closest('button.also');
    if (name) {  // the other source's name for what was searched, searched
      query.value = name.dataset.q;
      changed();
    }
    if (e.target.matches('button.like')) {  // the claims like a claim: the other source's, most alike first
      const claim = R.claims.find((c) => c.card === e.target.dataset.like);
      query.value = 'like:' + e.target.dataset.like;
      view = 'claims';
      topic = null;
      target = null;
      if (claim && claim.side >= 0 && sides.length === 2) side.value = String(1 - claim.side);
      order.value = 'relevance';
      show(true);
      query.scrollIntoView();
    }
    const link = e.target.closest('button.link');
    if (link) {  // a claim's or finding's own address, a step Back returns from
      target = {kind: view === 'claims' ? 'claim' : 'finding', id: link.dataset.link};
      remember(true);
      marked(link.closest('main > article'));
    }
    const every = e.target.closest('a[href="index.html"]');
    if (every && location.hash) {  // a split report's index, the address carried on (but the item linked)
      const kept = target;
      target = null;
      every.href = 'index.html' + (hashOf() ? '#' + hashOf() : '');
      target = kept;
    }
  });
  restore();
})();
