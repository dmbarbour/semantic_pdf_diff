// The report's search (report.js shows what it finds; docs/plans/portable-reports-2026-10-19.md, milestone 6): every
// word of a query found in the cards' fields, the most relevant first, by an index of the cards' words built in the
// page; by meaning too, where the report holds the claims' vectors (near:ID; like:ID blends them in). A card is read
// by its markup, as report.py's Cards.card writes it: its heading (file, section), its
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
  const GLOSSARY = 'glossary';  // the other names' kind that's the glossary's: each term with its meanings
  const STOP = new Set(('a an and are as at be by for from in into is it its of on or per than that the this to '
    + 'with').split(' '));
  const K1 = 1.2, B = 0.75;
  const LIKE_SHARE = 0.3;  // like:ID keeps the claims scoring at least this share of the claim's own score
  // by meaning (milestone 5; the embed lever's vectors), as measured: a claim near another at this cosine or more
  // (about 90% of judged counterparts, 5% of other claims), a typed query's (meaning:, the command line's) at this
  // share of the best; a cosine of 1 scores as much as this
  const NEAR_LEAST = 0.7, MEANING_SHARE = 0.65, MEANING_WEIGHT = 10;

  // words as searched: case and accents folded, numbers whole and plain ("1,000" is 1000, "15.00" is 15), letters
  // and digits apart ("75kW" is "75 kW")
  const fold = (text) => text.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
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
    const vocab = new Map(), postings = [], docs = [], pages = new Map(), cardDoc = new Map(), names = new Map();
    const values = new Map();  // doc: its claim's value, [kind, size of its unit, low, high] (report.py's)
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
        names.set(id, [plain(said[1]), plain(said[2])]);
        if (plain(said[4]).trim() !== 'unspecified') fields.push([CONDITIONS, plain(said[4])]);
        fields.push(...lines(said[5]).map((line) => [CONTEXT, line]), [QUOTE, plain(said[6])]);
      }
      fields.push(...lines(found[3]).map((line) => [CONTEXT, line]));
      const doc = add(fields);
      if (page) pages.set(doc, Number(page[1]));
      if (R.values && R.values[id]) values.set(doc, R.values[id]);
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
    // how much a term's words, in a row, weigh in a document (0: not found); a file's name only when asked for
    // (file:), or "mw" would find every claim of "nrel-5mw.pdf"
    // whole: the words are the field's, all of it (another name, matched as a claim's name)
    const weight = (sets, field, doc, whole = false) => {
      const {terms, fields} = docs[doc];
      let n = 0;
      for (let i = 0; i + sets.length <= terms.length; i++) {
        let j = 0;
        while (j < sets.length && sets[j].has(terms[i + j])) j++;
        if (whole && !((i === 0 || terms[i - 1] === -1) && terms[i + j] === -1)) continue;
        if (j === sets.length && (field === null ? fields[i] !== FILE : fields[i] === field)) n += WEIGHTS[fields[i]];
      }
      return n;
    };
    // whether a value [kind, size, low, high] is within a comparison's bounds: in its kind, converted, or as written
    // when the comparison names no unit
    const below = (a, b, open) => {
      const tolerance = 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));
      return open ? a < b - tolerance : a <= b + tolerance;
    };
    const within = (q, [kind, size, low, high]) => {
      if (q.kind !== null && kind !== q.kind) return false;
      const scale = q.kind === null ? 1 : size;
      const lo = low === null ? null : low * scale, hi = high === null ? null : high * scale;
      return (lo === null || q.hi === null || below(lo, q.hi, q.highOpen))
        && (q.lo === null || hi === null || below(q.lo, hi, q.lowOpen));
    };
    // the documents holding a term: {doc: its weight}
    const hits = (term) => {
      const out = new Map();
      if (term.unknown) return out;
      if (term.compare) {
        for (const [doc, value] of values) if (within(term.compare, value)) out.set(doc, 0);
        return out;
      }
      if (term.pages) {
        for (const [doc, page] of pages) if (page >= term.pages[0] && page <= term.pages[1]) out.set(doc, 0);
        return out;
      }
      const exact = (w) => new Set(vocab.has(w) ? [vocab.get(w)] : []);  // a whole name's words, as written
      const sets = term.terms ? [new Set(term.terms)]
        : term.words.map((w) => (term.whole ? exact(w) : new Set(expand(w))));
      if (sets.some((s) => !s.size)) return out;
      const size = (s) => [...s].reduce((sum, t) => sum + postings[t].length, 0);
      const rarest = sets.reduce((a, b) => (size(b) < size(a) ? b : a));
      for (const t of rarest) {
        for (const doc of postings[t]) {
          if (out.has(doc)) continue;
          const n = weight(sets, term.field, doc, term.whole);
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

    // the claims' vectors (the embed lever), read when first asked for: [signed bytes, their length]
    const vectors = new Map();
    const vectorOf = (id) => {
      if (!R.vectors || !Object.prototype.hasOwnProperty.call(R.vectors.of, id)) return null;
      if (!vectors.has(id)) {
        const bytes = atob(R.vectors.vectors[R.vectors.of[id]]), v = new Int8Array(bytes.length);
        let sum = 0;
        for (let i = 0; i < bytes.length; i++) {
          v[i] = (bytes.charCodeAt(i) << 24) >> 24;
          sum += v[i] * v[i];
        }
        vectors.set(id, [v, Math.sqrt(sum)]);
      }
      return vectors.get(id);
    };
    const cosines = ([v, length]) => {  // {doc: cosine} of every claim with a vector (search.py's embed.cosine)
      const out = new Map();
      for (const id of Object.keys(R.vectors ? R.vectors.of : {})) {
        const [w, other] = vectorOf(id);
        let dot = 0;
        for (let i = 0; i < w.length; i++) dot += v[i] * w[i];
        out.set(cardDoc.get(id), dot / (length * other || 1));
      }
      return out;
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
        const add = (doc, s) => out.set(doc, (out.get(doc) || 0) + s);
        for (const term of group.terms) {
          if (term.near !== undefined) {  // near:ID: the claims near it in meaning; not it
            const mine = vectorOf(term.near), self = cardDoc.get(term.near);
            for (const [doc, c] of mine ? cosines(mine) : []) {
              if (doc !== self && c >= NEAR_LEAST) add(doc, MEANING_WEIGHT * c);
            }
            continue;
          }
          if (term.meaning !== undefined) continue;  // a typed query's meaning: the command line's (search.py)
          if (term.like === undefined) {
            scores(term, out);
            continue;
          }
          // like:ID: the claims sharing enough of what makes it what it is, as it scores against itself; not it
          const alike = new Map(), self = cardDoc.get(term.like), kept = new Map();
          for (const one of about(term.like)) scores(one, alike);
          const least = LIKE_SHARE * (alike.get(self) || 0);
          for (const [doc, s] of alike) if (doc !== self && s >= least) kept.set(doc, s);
          const mine = vectorOf(term.like);
          if (!mine) {
            for (const [doc, s] of kept) add(doc, s);
            continue;
          }
          // with the claims' vectors, words and meaning blended (measured better than either): the words' share of
          // the best, and the cosine, for the claims either keeps
          const cos = cosines(mine), chosen = new Set(kept.keys());
          let best = 0;
          for (const s of kept.values()) best = Math.max(best, s);
          for (const [doc, c] of cos) if (doc !== self && c >= NEAR_LEAST) chosen.add(doc);
          for (const doc of chosen) {
            add(doc, MEANING_WEIGHT * ((kept.get(doc) || 0) / (best || 1) + (cos.get(doc) || 0)));
          }
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
    // a unit as the search reads it: [kind, size in its base], or null (report.py writes the tables)
    const unitOf = (text) => {
      const spelled = text.replace(/º/g, '°').normalize('NFKC').replace(/[·•⋅*×]/g, '.')  // values.spelled's
        .replace(/(?<=[A-Za-zµμ])-(?=[A-Za-z])/g, '.').replace(/\^/g, '').split(/\s+/).filter(Boolean).join(' ')
        .replace(/\.+$/, '');
      return (R.units && (R.units[spelled] || R.folded[spelled.toLowerCase()])) || null;
    };
    return {step, find, unitOf, embedded: () => Boolean(R.vectors && R.vectors.vectors.length),
            about: (id) => (step(), about(id).map((t) => word(t.terms[0]))),
            named: (id) => (step(), names.get(id) || ['', ''])};  // a card's entity and attribute
  };

  // a query: groups, each to be found (or, with "-", not), by any of its terms ("a OR b"); a term: words in a row (a
  // phrase), in one field or any; page:N or page:N-M; like:ID
  const TERM = /(-?)(?:([A-Za-z]+):)?(?:"([^"]*)"?|(\S+))/gu;
  // a value compared (milestone 3: ">50kW", "value:10-20mm", "value:0.075MW"): an operator, a number or a range,
  // and a unit, which may be the next word (">50 kW")
  const NUM = '[+-]?(?:\\d[\\d,]*(?:\\.\\d+)?|\\.\\d+)(?:[eE][+-]?\\d+)?';
  const COMPARED = new RegExp(`^(<=|>=|<|>|≤|≥)?\\s*(${NUM})(?:\\s*(?:–|-|to)\\s*(${NUM}))?\\s*(\\S.*)?$`);
  const number = (text) => Number(text.replace(/,/g, ''));
  // the term comparing a value, its bounds in its unit's base (or as written, without a unit); {unknown} for a unit
  // the search doesn't know
  const compared = (op, a, b, unitText, unitOf) => {
    let kind = null, size = 1;
    if (unitText) {
      const known = unitOf(unitText);
      if (!known) return {unknown: unitText};
      [kind, size] = known;
    }
    const x = number(a) * size, y = b === undefined ? null : number(b) * size;
    const q = {lo: x, hi: x, lowOpen: false, highOpen: false, kind};
    if (y !== null) Object.assign(q, {lo: Math.min(x, y), hi: Math.max(x, y)});
    else if (op === '>' || op === '>=' || op === '≥') Object.assign(q, {hi: null, lowOpen: op === '>'});
    else if (op) Object.assign(q, {lo: null, highOpen: op === '<'});
    return {compare: q};
  };
  const parse = (text, unitOf = () => null) => {
    const groups = [], tokens = [...text.matchAll(TERM)];
    let either = false;
    for (let i = 0; i < tokens.length; i++) {
      const [whole, not, name, quoted, bare] = tokens[i];
      if (!not && !name && quoted === undefined && (bare === 'OR' || bare === '|')) {
        either = groups.length > 0;
        continue;
      }
      const key = (name || '').toLowerCase(), raw = quoted === undefined ? bare : quoted;
      const value = (key === 'value' || (!key && quoted === undefined)) && COMPARED.exec(raw);
      let term = null;
      // a comparison: an operator, or value: with a range or a known unit ("value:3.5:1" stays words)
      const ranged = value && (value[3] !== undefined || (value[4] !== undefined && unitOf(value[4])));
      if (value && (value[1] || (key === 'value' && ranged))) {
        let unitText = value[4];
        const next = tokens[i + 1];
        if (!unitText && next && !next[1] && !next[2] && next[3] === undefined && unitOf(next[4])) {
          unitText = next[4];
          i++;
        }
        term = compared(value[1], value[2], value[3], unitText, unitOf);
      } else if (key === 'like') term = {like: raw};
      else if (key === 'near') term = {near: raw};
      else if (key === 'meaning') term = {meaning: raw};
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

  // whether a word is one a query asks for: letters by their beginnings, numbers (and a letter alone) whole
  const asks = (w, b) => (NUMBER.test(b) || b.length < 2 ? w === b : w.startsWith(b));
  const asked = (groups) => groups.filter((g) => !g.not).map((g) => g.terms.filter((t) => t.words));
  // whether a query names a name: finds it, and asks for every word it has ("rated output" names "rated output", not
  // "rated output limit"; words such as "of" aside)
  const names = (groups, text) => {
    const ws = words(text).filter((w) => !STOP.has(w)), terms = asked(groups).flat();
    return ws.length > 0 && covers(groups, text) && ws.every((w) => terms.some((t) => t.words.some((b) => asks(w, b))));
  };
  // the other names for what a query names (synonyms: {items, properties}, the model's groups of names, the
  // search_names lever; and glossary, each glossary term with its meanings), each with the query finding it and its
  // kind: the model's find claims whose item (or property) is that name, all of it and as written (not "diameter" in
  // "rotor diameter"); the glossary's, its words anywhere in a claim (an abbreviation is the same words: "side water
  // depth" finds "at an SWD of"); with the query's exclusions and its terms that aren't words (values, pages); none
  // for like:
  const otherNames = (groups, synonyms) => {
    const out = [];
    if (!synonyms || groups.some((g) => g.terms.some((t) => t.like !== undefined || t.near !== undefined))) return out;
    const kept = groups.filter((g) => g.not || !g.terms.some((t) => t.words));
    for (const [kind, field] of [['items', ENTITY], ['properties', ATTRIBUTE], [GLOSSARY, null]]) {
      for (const group of synonyms[kind] || []) {
        if (!group.some((n) => names(groups, n))) continue;
        for (const name of group) {
          const ws = words(name);
          if (!ws.length || names(groups, name) || out.some((o) => o.name === name)) continue;
          const term = field === null ? {words: ws, field} : {words: ws, field, whole: true};
          out.push({name, groups: [{not: false, terms: [term]}, ...kept], kind});
        }
      }
    }
    return out;
  };
  // the units a query names that the search doesn't know
  const unknown = (groups) => groups.flatMap((g) => g.terms.filter((t) => t.unknown).map((t) => t.unknown));
  // whether a name holds every word group a query asks for (fields, phrases' order and pages aside): one it finds
  const covers = (groups, text) => {
    const ws = words(text);
    const holds = (t) => t.words.every((b) => ws.some((w) => asks(w, b)));
    return asked(groups).every((terms) => !terms.length || terms.some(holds));
  };
  // whether a name holds any word a query asks for
  const touches = (groups, text) => {
    const ws = words(text);
    return asked(groups).some((terms) => terms.some((t) => t.words.some((b) => ws.some((w) => asks(w, b)))));
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
      return whole.has(w) || (!NUMBER.test(w) && begins.some((b) => asks(w, b)));
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

  return {index, parse, marker, covers, touches, names, otherNames, unknown, words, GLOSSARY};
})();
