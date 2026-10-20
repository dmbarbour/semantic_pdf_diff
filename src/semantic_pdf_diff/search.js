// The report's search (report.js shows what it finds; docs/plans/portable-reports-2026-10-19.md, milestone 6): every
// word of a query found in the cards' fields, the most relevant first, by an index of the cards' words built in the
// page. A card is read by its markup, as report.py's Cards.card writes it: its heading (file, section), its
// statement (entity — attribute, value and unit, conditions, frame and basis, quote) and its context lines. A
// finding's own text (why, its rationale) is a document beside its two cards'.
const Search = (() => {
  // fields, as a query names them, and what a word found in each weighs: what a claim is about first
  const WEIGHTS = [3, 3, 2, 1.5, 1.5, 1, 1, 0.5, 0.5];
  const [ENTITY, ATTRIBUTE, VALUE, CONDITIONS, SECTION, QUOTE, CONTEXT, FILE, OTHER] = WEIGHTS.keys();
  const NAMED = new Map(Object.entries({entity: ENTITY, attribute: ATTRIBUTE, attr: ATTRIBUTE, value: VALUE,
    unit: VALUE, conditions: CONDITIONS, condition: CONDITIONS, section: SECTION, heading: SECTION, quote: QUOTE,
    context: CONTEXT, file: FILE}));
  // the words like:ID looks for: what a claim is about, and its value's words ("UE — performs = resuming from
  // RRC_INACTIVE" is about its value), not its numbers
  const ABOUT = new Set([ENTITY, ATTRIBUTE, CONDITIONS, VALUE]);
  const STOP = new Set(('a an and are as at be by for from in into is it its of on or per than that the this to '
    + 'with').split(' '));
  const K1 = 1.2, B = 0.75;
  const LIKE_SHARE = 0.3;  // like:ID keeps the claims scoring at least this share of the claim's own score

  // words as searched: case and accents folded, numbers whole and plain ("1,000" is 1000, "15.00" is 15), letters
  // and digits apart ("75kW" is "75 kW")
  const fold = (text) => text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const NUMBER = /^\d/;
  const plainNumber = (n) => {
    const whole = n.replace(/,/g, '');
    return whole.includes('.') ? whole.replace(/0+$/, '').replace(/\.$/, '') : whole;
  };
  const norm = (w) => (NUMBER.test(w) ? plainNumber(w) : w);
  const WORD = /\d+(?:,\d{3}(?!\d))*(?:\.\d+)?|\p{L}+/gu;
  const words = (text) => (fold(text).match(WORD) || []).map(norm);

  const entities = {amp: '&', lt: '<', gt: '>', quot: '"', '#x27': "'"};
  const plain = (html) => html.replace(/<[^>]*>/g, ' ').replace(/&(amp|lt|gt|quot|#x27);/g, (m, e) => entities[e]);
  const CARD = /<h3>([\s\S]*?)<\/h3>\s*<div data-said="(\d+)"><\/div>([\s\S]*?)<small>/;
  const STATEMENT = new RegExp('^<b>([\\s\\S]*?) — ([\\s\\S]*?)</b><p>([\\s\\S]*?)</p><p>Conditions: ([\\s\\S]*?)</p>'
    + '([\\s\\S]*?)<blockquote>([\\s\\S]*?)</blockquote>$');
  const BOILERPLATE = /^\s*(Quote (not )?found|Read |Found \d+ times)/;  // the same on many cards: not searched
  const LABEL = /^\s*(As printed|Position|Frame|Basis): /;
  const lines = (html) => html.split('</p>').map(plain).filter((p) => p.trim() && !BOILERPLATE.test(p))
    .map((p) => p.replace(LABEL, ''));

  // R's index: each document's words in order, with their fields (-1 ends a field, so a phrase stays in one), and
  // each word's documents. Built a slice at a time (step), as the page has time.
  const index = (R) => {
    const vocab = new Map(), postings = [], docs = [], pages = new Map(), cardDoc = new Map();
    let sorted = null, average = 0;
    const add = (fields) => {  // [[field, text]...]: its document's number
      const id = docs.length, terms = [], of = [];
      let length = 0;
      for (const [field, text] of fields) {
        for (const w of words(text)) {
          let t = vocab.get(w);
          if (t === undefined) {
            t = vocab.size;
            vocab.set(w, t);
            postings.push([]);
          }
          if (postings[t][postings[t].length - 1] !== id) postings[t].push(id);
          terms.push(t);
          of.push(field);
          length += WEIGHTS[field];
        }
        terms.push(-1);
        of.push(field);
      }
      docs.push({terms: Int32Array.from(terms), fields: Uint8Array.from(of), length});
      return id;
    };
    const card = (id) => {
      const html = R.cards[id] || '', found = CARD.exec(html);
      if (!found) return add([[OTHER, plain(html)]]);
      const head = plain(found[1]).split(' · ');
      head.pop();  // its kind: the "Read as" filter's
      const page = /(\d+)\s*$/.exec(head.pop() || '');
      const section = head.length > 1 && head[head.length - 1].startsWith('§ ') ? head.pop().slice(2) : '';
      const fields = [[FILE, head.join(' · ')], [SECTION, section]];
      const said = STATEMENT.exec(R.said[Number(found[2])] || '');
      if (said) {
        fields.push([ENTITY, plain(said[1])], [ATTRIBUTE, plain(said[2])], [VALUE, plain(said[3])]);
        if (plain(said[4]).trim() !== 'unspecified') fields.push([CONDITIONS, plain(said[4])]);
        fields.push(...lines(said[5]).map((line) => [CONTEXT, line]), [QUOTE, plain(said[6])]);
      }
      fields.push(...lines(found[3]).map((line) => [CONTEXT, line]));
      const doc = add(fields);
      if (page) pages.set(doc, Number(page[1]));
      return doc;
    };
    // a finding's own words: why and its rationale, not what every finding of its relation or kind says
    const SAME = new RegExp(['<details>[\\s\\S]*?</details>', '<small>[\\s\\S]*?</small>', '<h2>[\\s\\S]*?</h2>',
      '<b>[\\s\\S]*?</b>', '<p class=[\'"]warning[\'"]>[\\s\\S]*?</p>'].join('|'), 'g');
    const finding = (f) => add([[OTHER, plain(f.html.replace(SAME, ''))]]);

    const ids = Object.keys(R.cards), total = ids.length + R.findings.length;
    let next = 0;
    // indexes some more, for about ms milliseconds (all of it without): whether it's all done
    const step = (ms = Infinity) => {
      const end = performance.now() + ms;
      while (next < total && performance.now() < end) {
        for (const stop = Math.min(total, next + 64); next < stop; next++) {
          if (next < ids.length) cardDoc.set(ids[next], card(ids[next]));
          else R.findings[next - ids.length].doc = finding(R.findings[next - ids.length]);
        }
      }
      if (next >= total && !sorted) {
        sorted = [...vocab.keys()].sort();
        average = docs.reduce((sum, d) => sum + d.length, 0) / Math.max(1, docs.length);
      }
      return next >= total;
    };
    const docsOf = (x) => (x.cards ? [cardDoc.get(x.cards[0]), cardDoc.get(x.cards[1]), x.doc] : [cardDoc.get(x.card)]);

    // a word's terms: those it begins (letters), or itself (a number, a letter alone: "m" isn't every word in m)
    const expand = (w) => {
      if (NUMBER.test(w) || w.length < 2) return vocab.has(w) ? [vocab.get(w)] : [];
      let lo = 0, hi = sorted.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (sorted[mid] < w) lo = mid + 1;
        else hi = mid;
      }
      const out = [];
      for (let i = lo; i < sorted.length && sorted[i].startsWith(w); i++) out.push(vocab.get(sorted[i]));
      return out;
    };
    // how much a term's words, in a row, weigh in a document (0: not found)
    const weight = (sets, field, doc) => {
      const {terms, fields} = docs[doc];
      let n = 0;
      for (let i = 0; i + sets.length <= terms.length; i++) {
        let j = 0;
        while (j < sets.length && sets[j].has(terms[i + j])) j++;
        if (j === sets.length && (field === null || fields[i] === field)) n += WEIGHTS[fields[i]];
      }
      return n;
    };
    // the documents holding a term: {doc: its weight}
    const hits = (term) => {
      const out = new Map();
      if (term.pages) {
        for (const [doc, page] of pages) if (page >= term.pages[0] && page <= term.pages[1]) out.set(doc, 0);
        return out;
      }
      const sets = term.terms ? [new Set(term.terms)] : term.words.map((w) => new Set(expand(w)));
      if (sets.some((s) => !s.size)) return out;
      const size = (s) => [...s].reduce((sum, t) => sum + postings[t].length, 0);
      const rarest = sets.reduce((a, b) => (size(b) < size(a) ? b : a));
      for (const t of rarest) {
        for (const doc of postings[t]) {
          if (out.has(doc)) continue;
          const n = weight(sets, term.field, doc);
          if (n > 0) out.set(doc, n);
        }
      }
      return out;
    };
    // like:ID's terms: the words saying what the claim is about, each its own term, weighing as its field does
    const about = (id) => {
      const doc = cardDoc.get(id);
      if (doc === undefined) return [];
      const {terms, fields} = docs[doc], out = new Map();
      terms.forEach((t, i) => {
        if (t >= 0 && ABOUT.has(fields[i])) out.set(t, Math.max(out.get(t) || 0, WEIGHTS[fields[i]] / WEIGHTS[ENTITY]));
      });
      return [...out].filter(([t]) => word(t).length > 1 && !STOP.has(word(t)) && !NUMBER.test(word(t)))
        .map(([t, boost]) => ({terms: [t], field: null, boost}));
    };
    const spelled = [];
    const word = (t) => {
      if (!spelled.length) for (const [w, i] of vocab) spelled[i] = w;
      return spelled[t];
    };

    // what a query's groups find: a function giving the items (findings or claims) found among some, {item: score}
    const find = (groups) => {
      step();
      const scores = (term, out) => {  // a term's documents, their BM25 scores added to out's
        const found = hits(term);
        const idf = Math.log(1 + (docs.length - found.size + 0.5) / (found.size + 0.5));
        for (const [doc, w] of found) {
          const s = w && (term.boost || 1) * idf * w * (K1 + 1) / (w + K1 * (1 - B + B * docs[doc].length / average));
          out.set(doc, (out.get(doc) || 0) + s);
        }
      };
      const scored = groups.map((group) => {
        const out = new Map();
        for (const term of group.terms) {
          if (term.like === undefined) {
            scores(term, out);
            continue;
          }
          // like:ID: the claims sharing enough of what makes it what it is, as it scores against itself; not it
          const alike = new Map(), self = cardDoc.get(term.like);
          for (const one of about(term.like)) scores(one, alike);
          const least = LIKE_SHARE * (alike.get(self) || 0);
          for (const [doc, s] of alike) if (doc !== self && s >= least) out.set(doc, (out.get(doc) || 0) + s);
        }
        return out;
      });
      return (items) => {
        const result = new Map();
        for (const x of items) {
          const ds = docsOf(x);
          let score = 0, kept = true;
          groups.forEach((group, g) => {
            let hit = false;
            for (const d of ds) {
              if (d !== undefined && scored[g].has(d)) {
                hit = true;
                score += group.not ? 0 : scored[g].get(d);
              }
            }
            if (hit === group.not) kept = false;
          });
          if (kept) result.set(x, score);
        }
        return result;
      };
    };
    return {step, find, about: (id) => (step(), about(id).map((t) => word(t.terms[0])))};
  };

  // a query: groups, each to be found (or, with "-", not), by any of its terms ("a OR b"); a term: words in a row (a
  // phrase), in one field or any; page:N or page:N-M; like:ID
  const TERM = /(-?)(?:([A-Za-z]+):)?(?:"([^"]*)"?|(\S+))/gu;
  const parse = (text) => {
    const groups = [];
    let either = false;
    for (const [whole, not, name, quoted, bare] of text.matchAll(TERM)) {
      if (!not && !name && quoted === undefined && (bare === 'OR' || bare === '|')) {
        either = groups.length > 0;
        continue;
      }
      const key = (name || '').toLowerCase(), raw = quoted === undefined ? bare : quoted;
      let term = null;
      if (key === 'like') term = {like: raw};
      else if (key === 'page') {
        const range = /^(\d+)(?:-(\d+))?$/.exec(raw);
        if (range) term = {pages: [Number(range[1]), Number(range[2] || range[1])]};
      } else {
        const ws = words(NAMED.has(key) ? raw : whole.replace(/^-/, ''));
        // a word such as "of" or "the", typed bare, isn't asked for: "power of the pump" finds "pump power"
        const asked = quoted !== undefined || ws.some((w) => !STOP.has(w));
        if (ws.length && asked) term = {words: ws, field: NAMED.has(key) ? NAMED.get(key) : null};
      }
      if (!term) continue;
      if (either && !not) groups[groups.length - 1].terms.push(term);
      else groups.push({not: Boolean(not), terms: [term]});
      either = false;
    }
    return groups;
  };

  // marks, in a part of the page, the words a query found: letters by their beginnings, numbers whole
  const RAW = /\d+(?:,\d{3}(?!\d))*(?:\.\d+)?|\p{L}[\p{L}\p{M}]*/gu;
  const marker = (groups, idx) => {
    const begins = [], whole = new Set();
    for (const group of groups.filter((g) => !g.not)) {
      for (const term of group.terms) {
        const ws = term.words || (term.like !== undefined ? idx.about(term.like) : []);
        for (const w of ws) {
          if (NUMBER.test(w)) whole.add(w);
          else if (term.like !== undefined) whole.add(w);
          else begins.push(w);
        }
      }
    }
    const hit = (raw) => {
      const w = norm(fold(raw));
      return whole.has(w) || (!NUMBER.test(w) && begins.some((b) => (b.length < 2 ? w === b : w.startsWith(b))));
    };
    return (part) => {
      const walker = document.createTreeWalker(part, NodeFilter.SHOW_TEXT), texts = [];
      while (walker.nextNode()) texts.push(walker.currentNode);
      for (const text of texts) {
        const parent = text.parentElement;
        if (!parent || parent.closest('button, select, mark')) continue;
        const value = text.nodeValue, pieces = [];
        let last = 0;
        for (const m of value.matchAll(RAW)) {
          if (!hit(m[0])) continue;
          pieces.push(value.slice(last, m.index));
          const mark = document.createElement('mark');
          mark.textContent = m[0];
          pieces.push(mark);
          last = m.index + m[0].length;
        }
        if (!pieces.length) continue;
        pieces.push(value.slice(last));
        text.replaceWith(...pieces);
      }
    };
  };

  return {index, parse, marker, words};
})();
