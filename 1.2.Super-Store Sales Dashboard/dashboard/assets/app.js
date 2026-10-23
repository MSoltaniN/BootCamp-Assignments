/* Superstore BI Dashboard — client layer.
 *
 * Everything on the page is computed here from the raw CSV embedded in the
 * document. Nothing is hardcoded: the KPI cards, the section-1 figures and all
 * seven charts read the same aggregate object, so the picture can never drift
 * from the numbers. Pressing "Rebuild from data" re-parses the CSV and re-runs
 * the whole pipeline in the browser.
 */
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  /* ------------------------------------------------------------------ data */

  function parseCSV(text) {
    var rows = [], row = [], field = '', inQ = false, i, c, n;
    for (i = 0; i < text.length; i++) {
      c = text[i];
      if (inQ) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else inQ = false;
        } else field += c;
      } else if (c === '"') inQ = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
      else if (c === '\r') { /* skip */ }
      else field += c;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    return rows;
  }

  function toRecords(csvText) {
    var table = parseCSV(csvText.replace(/^\uFEFF/, ''));
    var head = table[0], idx = {}, j;
    for (j = 0; j < head.length; j++) idx[head[j].trim()] = j;
    var need = ['Order ID', 'Order Date', 'Region', 'Category', 'Sub-Category',
      'Segment', 'State', 'Sales', 'Profit', 'Quantity', 'Discount', 'City'];
    for (j = 0; j < need.length; j++) {
      if (!(need[j] in idx)) throw new Error('missing column: ' + need[j]);
    }
    var out = [];
    for (var k = 1; k < table.length; k++) {
      var r = table[k];
      if (!r || r.length < head.length - 1 || !r[idx['Order ID']]) continue;
      var d = (r[idx['Order Date']] || '').trim();
      out.push({
        order: r[idx['Order ID']],
        date: d,
        month: d.slice(0, 7),
        year: d.slice(0, 4),
        region: (r[idx['Region']] || '').trim(),
        category: (r[idx['Category']] || '').trim(),
        sub: (r[idx['Sub-Category']] || '').trim(),
        segment: (r[idx['Segment']] || '').trim(),
        state: (r[idx['State']] || '').trim(),
        city: (r[idx['City']] || '').trim(),
        sales: +r[idx['Sales']] || 0,
        profit: +r[idx['Profit']] || 0,
        qty: +r[idx['Quantity']] || 0,
        disc: +r[idx['Discount']] || 0
      });
    }
    return out;
  }

  /* --------------------------------------------------------------- numbers */

  function money(v, digits) {
    var a = Math.abs(v), s;
    if (a >= 1e6) s = (a / 1e6).toFixed(1) + 'M';
    else if (a >= 1e3) s = (a / 1e3).toFixed(a >= 1e5 ? 1 : 1) + 'K';
    else s = a.toFixed(a >= 100 ? 0 : (digits || 0));
    if (s.indexOf('.') === 0) s = '0' + s;
    s = s.replace('.0K', 'K').replace('.0M', 'M');
    return (v < 0 ? '−$' : '$') + s;
  }

  function moneyExact(v) {
    return (v < 0 ? '−$' : '$') + Math.abs(v).toLocaleString('en-US',
      { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function pct(v, digits) {
    return (v * 100).toFixed(digits === undefined ? 1 : digits) + '%';
  }

  function num(v) { return v.toLocaleString('en-US'); }

  /* ------------------------------------------------------------ aggregation */

  function bump(map, key, dSales, dProfit, dQty) {
    var o = map.get(key);
    if (!o) { o = { sales: 0, profit: 0, qty: 0, orders: new Set() }; map.set(key, o); }
    o.sales += dSales; o.profit += dProfit; o.qty += dQty;
    return o;
  }

  function aggregate(recs, f) {
    var rows = recs.filter(function (r) {
      return (f.year === 'All' || r.year === f.year) &&
        (f.region === 'All' || r.region === f.region) &&
        (f.category === 'All' || r.category === f.category) &&
        (f.segment === 'All' || r.segment === f.segment);
    });

    var agg = {
      rows: rows,
      lineItems: rows.length,
      sales: 0, profit: 0, qty: 0,
      orders: new Set(),
      months: new Map(), regions: new Map(), cats: new Map(), subs: new Map(),
      states: new Map(), years: new Map(), matrix: new Map(), catSubs: new Map(),
      cities: 0
    };

    var citySet = new Set();
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      agg.sales += r.sales; agg.profit += r.profit; agg.qty += r.qty;
      agg.orders.add(r.order);
      citySet.add(r.city);
      bump(agg.months, r.month, r.sales, r.profit, r.qty);
      bump(agg.regions, r.region, r.sales, r.profit, r.qty);
      bump(agg.cats, r.category, r.sales, r.profit, r.qty);
      bump(agg.subs, r.sub, r.sales, r.profit, r.qty);
      bump(agg.states, r.state, r.sales, r.profit, r.qty);
      bump(agg.years, r.year, r.sales, r.profit, r.qty);
      bump(agg.matrix, r.region + '|' + r.category, r.sales, r.profit, r.qty);
      bump(agg.catSubs, r.category + '|' + r.sub, r.sales, r.profit, r.qty);
    }
    agg.cities = citySet.size;
    agg.orderCount = agg.orders.size;
    agg.margin = agg.sales ? agg.profit / agg.sales : 0;
    agg.avgOrder = agg.orderCount ? agg.sales / agg.orderCount : 0;
    agg.monthKeys = monthRange(rows);
    agg.empty = rows.length === 0;
    return agg;
  }

  function monthRange(rows) {
    if (!rows.length) return [];
    var min = '9999-99', max = '0000-00';
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].month < min) min = rows[i].month;
      if (rows[i].month > max) max = rows[i].month;
    }
    var out = [], y = +min.slice(0, 4), m = +min.slice(5, 7);
    var ey = +max.slice(0, 4), em = +max.slice(5, 7);
    while (y < ey || (y === ey && m <= em)) {
      out.push(y + '-' + String(m).padStart(2, '0'));
      m++; if (m > 12) { m = 1; y++; }
    }
    return out;
  }

  function sortedEntries(map, key) {
    return Array.from(map, function (p) {
      return { name: p[0], sales: p[1].sales, profit: p[1].profit, qty: p[1].qty };
    }).sort(function (a, b) { return b[key] - a[key]; });
  }

  /* ------------------------------------------------------------ svg helpers */

  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function tx(parent, x, y, str, o) {
    o = o || {};
    var t = el('text', {
      x: x, y: y,
      'font-size': o.size || 10,
      fill: o.fill || '#0f172a',
      'text-anchor': o.anchor || 'start',
      'font-weight': o.weight || 400,
      'dominant-baseline': o.baseline || 'middle',
      opacity: o.opacity === undefined ? 1 : o.opacity,
      'letter-spacing': o.spacing || 0,
      'font-family': o.mono ? 'Consolas, "Cascadia Mono", monospace' : '"Segoe UI", system-ui, sans-serif',
      stroke: o.halo ? '#ffffff' : null,
      'stroke-width': o.halo ? 3 : null,
      'paint-order': o.halo ? 'stroke' : null
    }, parent);
    t.textContent = str;
    return t;
  }

  function frame(host) {
    host.innerHTML = '';
    var w = host.clientWidth || 400, h = host.clientHeight || 200;
    var s = el('svg', { width: w, height: h, viewBox: '0 0 ' + w + ' ' + h }, host);
    return { s: s, w: w, h: h };
  }

  function hex(h) {
    return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  }

  function mix(a, b, t) {
    t = Math.max(0, Math.min(1, t));
    var A = hex(a), B = hex(b);
    return 'rgb(' + Math.round(A[0] + (B[0] - A[0]) * t) + ',' +
      Math.round(A[1] + (B[1] - A[1]) * t) + ',' +
      Math.round(A[2] + (B[2] - A[2]) * t) + ')';
  }

  function emptyNote(host, msg) {
    var f = frame(host);
    tx(f.s, f.w / 2, f.h / 2, msg, { anchor: 'middle', fill: '#94a3b8', size: 11 });
  }

  /* ----------------------------------------------------------------- charts */

  var BLUE = '#1d4ed8', BLUE_SOFT = '#c7d8fb', GREEN = '#15803d', RED = '#dc2626',
    NAVY = '#0f2a63', INK = '#0f172a', MUTED = '#64748b', FAINT = '#94a3b8', LINE = '#e8ecf2';

  var CAT_COLOR = {
    'Office Supplies': '#1d4ed8',
    'Technology': '#7c3aed',
    'Furniture': '#f59e0b'
  };
  var CAT_FALLBACK = ['#1d4ed8', '#7c3aed', '#f59e0b', '#0d9488', '#be123c'];

  function catColor(name, i) { return CAT_COLOR[name] || CAT_FALLBACK[i % CAT_FALLBACK.length]; }

  /* --- 1. sales bars + profit line ------------------------------------- */

  function drawTrend(host, agg) {
    if (agg.empty) return emptyNote(host, 'No orders match the current filters');
    var f = frame(host), s = f.s;
    var m = { l: 56, r: 44, t: 15, b: 21 };
    var pw = f.w - m.l - m.r;
    var avail = f.h - m.t - m.b;
    var gap = 17;
    var hTop = (avail - gap) * 0.57, hBot = (avail - gap) - hTop;
    var yTop = m.t, yBot = m.t + hTop + gap;

    var keys = agg.monthKeys, n = keys.length;
    var vals = keys.map(function (k) {
      var o = agg.months.get(k);
      return { k: k, s: o ? o.sales : 0, p: o ? o.profit : 0 };
    });

    var rawMax = Math.max.apply(null, vals.map(function (v) { return v.s; }).concat([1]));
    var ticks = 4, step = niceStep(rawMax / ticks);
    while (step * ticks < rawMax) step = niceStep(step * 1.6);
    var maxS = step * ticks;

    var ps = vals.map(function (v) { return v.p; });
    var maxP = Math.max.apply(null, ps.concat([0]));
    var minP = Math.min.apply(null, ps.concat([0]));
    // symmetric round domain: a profit panel needs a readable tick at each end,
    // and zero must stay in the middle or the loss shading lies
    var lim = niceStep(Math.max(Math.abs(maxP), Math.abs(minP)) * 1.06) || 1;
    maxP = lim; minP = -lim;

    var xs = function (i) { return m.l + (pw * (i + 0.5)) / n; };
    var ys = function (v) { return yTop + hTop - (v / maxS) * hTop; };
    var yp = function (v) { return yBot + hBot - ((v - minP) / (maxP - minP)) * hBot; };

    // --- sales panel gridlines -------------------------------------------
    for (var g = 0; g <= ticks; g++) {
      var v = step * g, y = ys(v);
      el('line', { x1: m.l, x2: m.l + pw, y1: y, y2: y, stroke: g === 0 ? '#cbd5e1' : LINE, 'stroke-width': 1 }, s);
      tx(s, m.l - 7, y, money(v), { anchor: 'end', size: 8.5, fill: FAINT });
    }

    // --- profit panel gridlines -----------------------------------------
    el('line', { x1: m.l, x2: m.l + pw, y1: yp(0), y2: yp(0), stroke: '#cbd5e1', 'stroke-width': 1 }, s);
    tx(s, m.l - 7, yp(0), '$0', { anchor: 'end', size: 8.5, fill: FAINT });
    tx(s, m.l - 7, yp(maxP) + 2, money(maxP), { anchor: 'end', size: 8, fill: '#b6bec9' });
    tx(s, m.l - 7, yp(minP) - 2, money(minP), { anchor: 'end', size: 8, fill: '#b6bec9' });

    // rotated axis titles: the two panels carry different scales, so each one
    // says what it measures instead of pretending to share an axis
    axisTitle(s, 12, yTop + hTop / 2, 'SALES ($)');
    axisTitle(s, 12, yBot + hBot / 2, 'PROFIT ($)');

    // --- year separators across both panels ------------------------------
    var prevYear = null;
    vals.forEach(function (v, i) {
      var yr = v.k.slice(0, 4);
      if (yr !== prevYear) {
        if (prevYear !== null) {
          var x = m.l + (pw * i) / n;
          el('line', { x1: x, x2: x, y1: yTop, y2: yBot + hBot, stroke: '#dde3ec', 'stroke-width': 1 }, s);
        }
        tx(s, m.l + (pw * (i + 0.5)) / n, yTop - 8, yr,
          { anchor: 'middle', size: 9, weight: 600, fill: MUTED, spacing: 0.5 });
        prevYear = yr;
      }
    });

    // --- loss shading in the profit panel --------------------------------
    var bandStart = null;
    for (var i = 0; i <= vals.length; i++) {
      var neg = i < vals.length && vals[i].p < 0;
      if (neg && bandStart === null) bandStart = i;
      if (!neg && bandStart !== null) {
        var bx0 = m.l + (pw * bandStart) / n;
        var bx1 = m.l + (pw * i) / n;
        el('rect', { x: bx0, y: yBot, width: Math.max(1.5, bx1 - bx0), height: hBot, fill: '#fef1f1' }, s);
        bandStart = null;
      }
    }

    // --- sales bars ------------------------------------------------------
    var bw = Math.max(3, Math.min(16, (pw / n) * 0.64));
    vals.forEach(function (v, i) {
      var y = ys(v.s), h = yTop + hTop - y;
      el('rect', {
        x: xs(i) - bw / 2, y: y, width: bw, height: Math.max(0.8, h),
        fill: v.p < 0 ? '#a9c0ef' : BLUE_SOFT, rx: 1.5
      }, s);
    });

    // --- profit line + area ----------------------------------------------
    var line = vals.map(function (v, i) {
      return (i ? 'L' : 'M') + xs(i).toFixed(1) + ' ' + yp(v.p).toFixed(1);
    }).join(' ');
    var area = 'M ' + xs(0).toFixed(1) + ' ' + yp(0).toFixed(1) + ' ' +
      line.replace(/^M/, 'L') + ' L ' + xs(n - 1).toFixed(1) + ' ' + yp(0).toFixed(1) + ' Z';

    var defs = el('defs', {}, s);
    var cpPos = el('clipPath', { id: 'tr-clip-pos' }, defs);
    el('rect', { x: m.l, y: yBot, width: pw, height: Math.max(0, yp(0) - yBot) }, cpPos);
    var cpNeg = el('clipPath', { id: 'tr-clip-neg' }, defs);
    el('rect', { x: m.l, y: yp(0), width: pw, height: Math.max(0, yBot + hBot - yp(0)) }, cpNeg);

    el('path', { d: area, fill: '#1d4ed8', opacity: 0.13, 'clip-path': 'url(#tr-clip-pos)' }, s);
    el('path', { d: area, fill: '#dc2626', opacity: 0.16, 'clip-path': 'url(#tr-clip-neg)' }, s);
    el('path', { d: line, fill: 'none', stroke: NAVY, 'stroke-width': 1.8, 'stroke-linejoin': 'round' }, s);

    // --- annotate the extremes -------------------------------------------
    var best = 0, worst = 0;
    vals.forEach(function (v, i) { if (v.p > vals[best].p) best = i; if (v.p < vals[worst].p) worst = i; });
    [best, worst].forEach(function (i) {
      el('circle', { cx: xs(i), cy: yp(vals[i].p), r: 3, fill: '#fff', stroke: NAVY, 'stroke-width': 1.8 }, s);
    });
    if (vals[best].p > 0) {
      tx(s, xs(best), Math.max(yBot + 9, yp(vals[best].p) - 11), money(vals[best].p),
        { anchor: 'middle', size: 8.5, weight: 650, fill: GREEN, halo: true });
    }
    if (vals[worst].p < 0) {
      // keep the trough marker visible: annotate into the empty wedge above-left
      tx(s, xs(worst) - 7, Math.max(yBot + 8, yp(vals[worst].p) - 12), money(vals[worst].p),
        { anchor: 'end', size: 8.5, weight: 650, fill: RED, halo: true });
    }

    // --- x labels ---------------------------------------------------------
    vals.forEach(function (v, i) {
      if (v.k.slice(5) === '01' || i === 0) {
        tx(s, xs(i), yBot + hBot + 11, shortMonth(v.k), { anchor: 'middle', size: 8.5, fill: FAINT });
      }
    });
  }

  function axisTitle(parent, x, y, str) {
    var t = tx(parent, 0, 0, str, { anchor: 'middle', size: 7.5, weight: 700, fill: '#b6bec9', spacing: 0.9 });
    t.setAttribute('transform', 'translate(' + x + ',' + y + ') rotate(-90)');
    return t;
  }

  function shortMonth(k) {
    var names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return names[+k.slice(5, 7) - 1] + " '" + k.slice(2, 4);
  }

  function niceStep(v) {
    if (!(v > 0)) return 1;
    var p = Math.pow(10, Math.floor(Math.log10(v)));
    var n = v / p;
    var cands = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
    for (var i = 0; i < cands.length; i++) if (n <= cands[i]) return cands[i] * p;
    return 10 * p;
  }

  /* --- 2. category + sub-category in one hierarchical chart ------------- */

  function drawCatSub(host, agg) {
    if (agg.empty) return emptyNote(host, 'No data in scope');
    var f = frame(host), s = f.s;

    // group sub-categories under their parent category
    var groups = [];
    var byName = {};
    agg.cats.forEach(function (v, name) {
      var g = { name: name, sales: v.sales, profit: v.profit, subs: [] };
      groups.push(g);
      byName[name] = g;
    });
    groups.sort(function (a, b) { return b.profit - a.profit; });

    agg.catSubs.forEach(function (v, key) {
      var cut = key.indexOf('|');
      var g = byName[key.slice(0, cut)];
      if (!g) return;
      g.subs.push({ name: key.slice(cut + 1), sales: v.sales, profit: v.profit });
    });
    groups.forEach(function (g) {
      g.subs.sort(function (a, b) { return b.profit - a.profit; });
    });

    var totalSales = agg.sales || 1;
    groups.forEach(function (g) {
      g.margin = g.sales ? g.profit / g.sales : 0;
      g.stats = pct(g.sales / totalSales, 0) + ' sales · ' + pct(g.margin, 1) + ' margin';
    });

    var nSubs = 0;
    groups.forEach(function (g) { nSubs += g.subs.length; });

    // The label column has to fit "name + share + margin" or the text runs into
    // the bars. Measure the widest header line instead of guessing a constant.
    var widest = 0;
    groups.forEach(function (g) {
      var w = 13 + g.name.length * 5.15 + 6 + g.stats.length * 3.5;
      if (w > widest) widest = w;
    });
    var m = { l: Math.min(214, Math.max(108, widest + 10)), r: 48, t: 2, b: 2 };
    var pw = f.w - m.l - m.r;
    var availH = f.h - m.t - m.b;
    var unit = availH / (nSubs + groups.length * 1.55);
    var headH = unit * 1.55;

    var maxAbs = 1;
    groups.forEach(function (g) {
      maxAbs = Math.max(maxAbs, Math.abs(g.profit));
      g.subs.forEach(function (d) { maxAbs = Math.max(maxAbs, Math.abs(d.profit)); });
    });

    var negW = pw * 0.19, posW = pw * 0.79;
    var x0 = m.l + negW;
    var sx = function (v) {
      return v >= 0 ? x0 + (v / maxAbs) * posW : x0 - (Math.abs(v) / maxAbs) * negW * 0.94;
    };

    var y = m.t;
    groups.forEach(function (g, gi) {
      var col = catColor(g.name, gi);

      // --- category row: one summary bar, the parent level of the hierarchy
      el('rect', { x: 2, y: y, width: f.w - 4, height: headH - 1, fill: '#f5f8fd', rx: 3 }, s);
      el('rect', { x: 2, y: y, width: 3, height: headH - 1, fill: col, rx: 1.5 }, s);
      tx(s, 10, y + headH / 2, g.name, { size: 9, weight: 700, fill: '#0f172a' });

      // the bar is profit, so a high-revenue / no-profit category gets a tiny bar:
      // the margin has to sit next to the name or that reads as a rendering bug
      tx(s, 13 + g.name.length * 5.15, y + headH / 2, g.stats, {
        size: 6.9,
        fill: Math.abs(g.margin) < 0.02 ? '#b45309' : FAINT,
        weight: Math.abs(g.margin) < 0.02 ? 700 : 400
      });

      var bwid = Math.abs(sx(g.profit) - x0);
      el('rect', {
        x: Math.min(x0, sx(g.profit)), y: y + headH * 0.22,
        width: Math.max(1.5, bwid), height: headH * 0.56, rx: 2, fill: col
      }, s);
      tx(s, g.profit < 0 ? x0 - bwid - 4 : x0 + bwid + 4, y + headH / 2,
        money(g.profit), { anchor: g.profit < 0 ? 'end' : 'start', size: 9, weight: 700, fill: col });
      y += headH;

      // --- sub-category rows: the child level, indented and lighter
      g.subs.forEach(function (d) {
        var cy = y + unit / 2;
        tx(s, 24, cy, d.name, { size: 8.2, fill: d.profit < 0 ? '#7f1d1d' : '#475569' });
        var w = Math.abs(sx(d.profit) - x0);
        el('rect', {
          x: Math.min(x0, sx(d.profit)), y: cy - unit * 0.30,
          width: Math.max(0.8, w), height: unit * 0.60, rx: 1,
          fill: d.profit < 0 ? RED : mix('#ffffff', col, 0.55)
        }, s);
        tx(s, d.profit < 0 ? x0 - w - 4 : x0 + w + 4, cy, money(d.profit),
          { anchor: d.profit < 0 ? 'end' : 'start', size: 7.8, weight: 600, fill: d.profit < 0 ? RED : '#334155' });
        y += unit;
      });
    });

    // zero line on top of the bars so the sign of every bar is unambiguous
    el('line', { x1: x0, x2: x0, y1: m.t, y2: y + 1, stroke: '#8794a8', 'stroke-width': 1 }, s);
  }

  /* --- 3. margin by discount depth -------------------------------------- */

  function drawDiscount(host, agg) {
    if (agg.empty) return emptyNote(host, 'No data in scope');
    var f = frame(host), s = f.s;

    // Band edges must be inclusive on the lower bound: a 30% discount belongs to
    // "30-49%", not to "21-30%", or the chart and the written insight disagree
    // about what "30% or more" earned.
    var defs = [
      { label: '0%', test: function (d) { return d <= 1e-9; } },
      { label: '1-9%', test: function (d) { return d > 1e-9 && d < 0.10; } },
      { label: '10-19%', test: function (d) { return d >= 0.10 && d < 0.20; } },
      { label: '20-29%', test: function (d) { return d >= 0.20 && d < 0.30; } },
      { label: '30-49%', test: function (d) { return d >= 0.30 && d < 0.50; } },
      { label: '50%+', test: function (d) { return d >= 0.50; } }
    ];
    var rows = defs.map(function (b) {
      return { label: b.label, test: b.test, sales: 0, profit: 0, n: 0 };
    });
    agg.rows.forEach(function (r) {
      for (var i = 0; i < rows.length; i++) {
        if (rows[i].test(r.disc)) {
          rows[i].sales += r.sales; rows[i].profit += r.profit; rows[i].n++;
          break;
        }
      }
    });
    var kept = rows.filter(function (r) { return r.n > 0; });
    rows = kept;
    rows.forEach(function (r) { r.margin = r.sales ? r.profit / r.sales : 0; });

    var m = { l: 34, r: 10, t: 15, b: 27 };
    var pw = f.w - m.l - m.r, ph = f.h - m.t - m.b;

    var lo = Math.min.apply(null, rows.map(function (r) { return r.margin; }).concat([0]));
    var hi = Math.max.apply(null, rows.map(function (r) { return r.margin; }).concat([0]));
    var pad = ((hi - lo) || 0.2) * 0.12;
    lo -= pad; hi += pad;
    var yv = function (v) { return m.t + ph - ((v - lo) / (hi - lo)) * ph; };
    var yz = yv(0);

    el('line', { x1: m.l, x2: m.l + pw, y1: yz, y2: yz, stroke: '#cbd5e1', 'stroke-width': 1 }, s);
    tx(s, m.l - 5, yz, '0%', { anchor: 'end', size: 7.5, fill: FAINT });

    var totalSales = agg.sales || 1;
    var stepw = pw / rows.length;
    var bw = Math.min(58, stepw * 0.5);

    rows.forEach(function (r, i) {
      var cx = m.l + stepw * (i + 0.5);
      var x1 = yv(r.margin);
      var fill = r.margin >= 0 ? GREEN : RED;

      el('rect', {
        x: cx - bw / 2, y: Math.min(yz, x1), width: bw, height: Math.max(1, Math.abs(x1 - yz)),
        rx: 2, fill: fill
      }, s);

      tx(s, cx, r.margin >= 0 ? x1 - 6 : x1 + 7, pct(r.margin, 1),
        { anchor: 'middle', size: 8.2, weight: 650, fill: fill, halo: true });

      tx(s, cx, m.t + ph + 9, r.label, { anchor: 'middle', size: 7.8, weight: 600, fill: '#475569' });
      tx(s, cx, m.t + ph + 18, pct(r.sales / totalSales, 0) + ' rev',
        { anchor: 'middle', size: 6.6, fill: FAINT });
    });
  }

  /* --- 4. state tile grid map ------------------------------------------- */

  var TILES = [
    ['AK', 0, 0], ['ME', 10, 0],
    ['VT', 9, 1], ['NH', 10, 1],
    ['WA', 0, 2], ['ID', 1, 2], ['MT', 2, 2], ['ND', 3, 2], ['MN', 4, 2], ['WI', 6, 2],
    ['MI', 7, 2], ['NY', 8, 2], ['MA', 10, 2],
    ['OR', 0, 3], ['NV', 1, 3], ['WY', 2, 3], ['SD', 3, 3], ['IA', 4, 3], ['IL', 5, 3],
    ['IN', 6, 3], ['OH', 7, 3], ['PA', 8, 3], ['NJ', 9, 3], ['CT', 10, 3],
    ['CA', 0, 4], ['UT', 1, 4], ['CO', 2, 4], ['NE', 3, 4], ['MO', 4, 4], ['KY', 5, 4],
    ['WV', 6, 4], ['VA', 7, 4], ['MD', 8, 4], ['DE', 9, 4], ['RI', 10, 4],
    ['AZ', 1, 5], ['NM', 2, 5], ['KS', 3, 5], ['AR', 4, 5], ['TN', 5, 5], ['NC', 6, 5],
    ['SC', 7, 5], ['DC', 8, 5],
    ['OK', 3, 6], ['LA', 4, 6], ['MS', 5, 6], ['AL', 6, 6], ['GA', 7, 6],
    ['HI', 0, 7], ['TX', 2, 7], ['FL', 9, 7]
  ];

  var STATE_NAME = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'District of Columbia': 'DC',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL',
    'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
    'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
    'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR',
    'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD',
    'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA',
    'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY'
  };

  function drawMap(host, agg) {
    var f = frame(host), s = f.s;
    var byAbbr = {};
    agg.states.forEach(function (v, k) {
      var ab = STATE_NAME[k] || k;
      byAbbr[ab] = { sales: v.sales, profit: v.profit, name: k };
    });
    var maxS = 0;
    for (var a in byAbbr) maxS = Math.max(maxS, byAbbr[a].sales);

    var cols = 11, rows = 8;
    var legendH = 15, padTop = 1;
    var cell = Math.min((f.w - 6) / cols, (f.h - legendH - padTop) / rows);
    var gap = Math.max(1.5, cell * 0.07);
    var gx = (f.w - cell * cols) / 2;
    var gy = padTop;

    TILES.forEach(function (t) {
      var ab = t[0], col = t[1], row = t[2];
      var x = gx + col * cell + gap / 2, y = gy + row * cell + gap / 2;
      var sz = cell - gap;
      var d = byAbbr[ab];
      var fill = '#f1f4f9';
      if (d && d.sales > 0 && maxS > 0) {
        var t2 = Math.pow(d.sales / maxS, 0.62);
        fill = mix('#e8eefc', '#1e3fa8', t2);
      }
      var lab = '#94a3b8';
      if (d && d.sales > 0 && maxS > 0) {
        var tt = Math.pow(d.sales / maxS, 0.62);
        lab = tt > 0.55 ? '#ffffff' : '#1e293b';
      }
      el('rect', { x: x, y: y, width: sz, height: sz, rx: Math.max(1.5, sz * 0.12), fill: fill }, s);
      tx(s, x + sz / 2, y + sz / 2, ab, {
        anchor: 'middle', size: Math.max(6.2, Math.min(9, sz * 0.28)),
        weight: 600, fill: lab
      });
    });

    // gradient legend
    var lw = Math.min(64, f.w * 0.18), lh = 5;
    var lx = f.w - 50 - lw, ly = f.h - 7;
    for (var i = 0; i < lw; i += 2) {
      el('rect', { x: lx + i, y: ly, width: 2.4, height: lh, fill: mix('#e8eefc', '#1e3fa8', i / lw) }, s);
    }
    tx(s, lx - 6, ly + lh / 2, '$0', { anchor: 'end', size: 7.5, fill: FAINT });
    tx(s, f.w - 4, ly + lh / 2, money(maxS), { anchor: 'end', size: 7.5, fill: FAINT });
  }

  /* --- 5. top states ---------------------------------------------------- */

  function drawStates(host, agg) {
    if (agg.empty) return emptyNote(host, 'No data in scope');
    var f = frame(host), s = f.s;
    var rows = sortedEntries(agg.states, 'sales').slice(0, 10);
    var m = { l: 4, r: 8, t: 6, b: 6 };
    var pw = f.w - m.l - m.r, ph = f.h - m.t - m.b;
    var rh = ph / rows.length;
    var max = Math.max.apply(null, rows.map(function (r) { return r.sales; }).concat([1]));
    var barMax = pw - 74;
    var best = 0;
    rows.forEach(function (r, i) { if (r.profit > rows[best].profit) best = i; });

    rows.forEach(function (r, i) {
      var y = m.t + i * rh, cy = y + rh / 2, bh = Math.max(6, rh * 0.52);
      el('rect', { x: m.l, y: cy - bh / 2, width: barMax, height: bh, rx: 2, fill: '#f2f5fa' }, s);
      el('rect', {
        x: m.l, y: cy - bh / 2, width: Math.max(2, (r.sales / max) * barMax), height: bh,
        rx: 2, fill: i === 0 ? BLUE : mix('#c7d8fb', '#3b64c9', 0.35 + 0.06 * i)
      }, s);
      tx(s, m.l + 5, cy, r.name, { size: 8.5, weight: 600, fill: i < 3 ? '#ffffff' : '#0f172a' });
      tx(s, m.l + barMax + pw * 0.0 + 8, cy - 3, money(r.sales), { size: 8.5, weight: 600, fill: INK });
      tx(s, m.l + barMax + 8, cy + 6, money(r.profit) + ' profit',
        { size: 7.5, fill: r.profit < 0 ? RED : GREEN });
    });
  }

  /* --- 6. region x category heatmap ------------------------------------- */

  function drawHeat(host, agg) {
    if (agg.empty) return emptyNote(host, 'No data in scope');
    var f = frame(host), s = f.s;
    var cats = ['Furniture', 'Office Supplies', 'Technology'];
    var regions = ['Central', 'East', 'South', 'West'];
    var m = { l: 92, r: 6, t: 18, b: 4 };
    var cw = (f.w - m.l - m.r) / regions.length;
    var ch = (f.h - m.t - m.b) / cats.length;
    var vals = [], key;
    for (var i = 0; i < cats.length; i++) {
      for (var j = 0; j < regions.length; j++) {
        var o = agg.matrix.get(regions[j] + '|' + cats[i]);
        vals.push(o ? o.profit : 0);
      }
    }
    var maxAbs = Math.max.apply(null, vals.map(Math.abs).concat([1]));

    for (j = 0; j < regions.length; j++) {
      tx(s, m.l + cw * (j + 0.5), m.t - 8, regions[j], { anchor: 'middle', size: 8.5, weight: 600, fill: MUTED });
    }
    for (i = 0; i < cats.length; i++) {
      tx(s, m.l - 8, m.t + ch * (i + 0.5), cats[i], { anchor: 'end', size: 8.5, weight: 600, fill: MUTED });
      for (j = 0; j < regions.length; j++) {
        key = regions[j] + '|' + cats[i];
        var o2 = agg.matrix.get(key);
        var v = o2 ? o2.profit : 0;
        var t = Math.pow(Math.abs(v) / maxAbs, 0.7);
        var fill = v >= 0 ? mix('#fdfefe', '#15803d', t) : mix('#fffdfd', '#dc2626', t);
        var txtCol = t > 0.5 ? '#ffffff' : (v >= 0 ? '#14532d' : '#7f1d1d');
        el('rect', {
          x: m.l + cw * j + 2, y: m.t + ch * i + 2,
          width: cw - 4, height: ch - 4, rx: 3, fill: fill
        }, s);
        tx(s, m.l + cw * (j + 0.5), m.t + ch * (i + 0.5) - 4, money(v),
          { anchor: 'middle', size: 9.5, weight: 650, fill: txtCol });
        tx(s, m.l + cw * (j + 0.5), m.t + ch * (i + 0.5) + 6,
          o2 ? pct(o2.profit / o2.sales) + ' margin' : '—',
          { anchor: 'middle', size: 7.5, fill: txtCol, opacity: 0.85 });
      }
    }
  }

  /* --- 7. profit by year ------------------------------------------------ */

  function drawYear(host, agg) {
    if (agg.empty) return emptyNote(host, 'No data in scope');
    var f = frame(host), s = f.s;
    var years = Array.from(agg.years.keys()).sort();
    var rows = years.map(function (y) { return { y: y, p: agg.years.get(y).profit, s: agg.years.get(y).sales }; });
    var m = { l: 6, r: 6, t: 14, b: 18 };
    var pw = f.w - m.l - m.r, ph = f.h - m.t - m.b;
    var max = Math.max.apply(null, rows.map(function (r) { return Math.max(0, r.p); }).concat([1]));
    var min = Math.min.apply(null, rows.map(function (r) { return Math.min(0, r.p); }).concat([0]));
    var span = max - min || 1;
    var yz = function (v) { return m.t + ph - ((v - min) / span) * ph; };
    var bw = Math.min(52, (pw / rows.length) * 0.55);
    var bestI = 0;
    rows.forEach(function (r, i) { if (r.p > rows[bestI].p) bestI = i; });

    el('line', { x1: m.l, x2: m.l + pw, y1: yz(0), y2: yz(0), stroke: '#cbd5e1' }, s);
    rows.forEach(function (r, i) {
      var cx = m.l + (pw * (i + 0.5)) / rows.length;
      var y0 = yz(0), y1 = yz(r.p);
      el('rect', {
        x: cx - bw / 2, y: Math.min(y0, y1), width: bw, height: Math.max(1.5, Math.abs(y1 - y0)),
        rx: 2, fill: i === bestI ? GREEN : '#9ec7ae'
      }, s);
      tx(s, cx, Math.min(y0, y1) - 6, money(r.p),
        { anchor: 'middle', size: 8.5, weight: 650, fill: i === bestI ? GREEN : MUTED });
      tx(s, cx, m.t + ph + 9, r.y, { anchor: 'middle', size: 8.5, fill: FAINT, weight: 600 });
    });
  }

  /* ------------------------------------------------------------------ KPIs */

  function renderKPIs(agg) {
    var host = document.getElementById('kpis');
    var cats = sortedEntries(agg.cats, 'profit');
    var regions = sortedEntries(agg.regions, 'sales');
    var subs = sortedEntries(agg.subs, 'profit');
    var years = Array.from(agg.years.entries()).map(function (p) { return { y: p[0], p: p[1].profit }; })
      .sort(function (a, b) { return b.p - a.p; });

    var topRegion = regions[0];
    var worstSub = subs[subs.length - 1];
    var bestYear = years[0];
    var bestCat = cats[0];

    var cards = [
      {
        label: 'Total sales', cls: '', value: money(agg.sales),
        foot: '<b>' + moneyExact(agg.sales) + '</b> · ' + num(agg.lineItems) + ' line items',
        key: 'sales'
      },
      {
        label: 'Total profit', cls: agg.profit >= 0 ? 'pos' : 'neg', value: money(agg.profit),
        foot: '<b>' + moneyExact(agg.profit) + '</b> · ' + pct(agg.profit / (agg.sales || 1), 2) + ' of sales',
        key: 'profit'
      },
      {
        label: 'Orders', cls: '', value: num(agg.orderCount),
        foot: 'avg order <b>' + money(agg.avgOrder) + '</b>',
        key: 'orders'
      },
      {
        label: 'Profit margin', cls: agg.margin >= 0 ? 'pos' : 'neg', value: pct(agg.margin, 1),
        foot: 'profit ÷ sales · <b>' + num(agg.qty) + '</b> units',
        key: 'margin'
      },
      {
        label: 'Top region', cls: 'amber', value: topRegion ? topRegion.name : '—', small: true,
        foot: topRegion ? '<b>' + money(topRegion.sales) + '</b> sales · ' + money(topRegion.profit) + ' profit' : '—',
        key: 'topRegion'
      },
      {
        label: 'Biggest loss driver', cls: 'neg', value: worstSub ? worstSub.name : '—', small: true,
        foot: worstSub ? '<b>' + money(worstSub.profit) + '</b> profit · ' + money(worstSub.sales) + ' sales' : '—',
        key: 'worstSub'
      }
    ];

    host.innerHTML = cards.map(function (c) {
      return '<div class="kpi ' + c.cls + '" data-k="' + c.key + '">' +
        '<div class="k-label">' + c.label + '</div>' +
        '<div class="k-value' + (c.small ? ' sm' : '') + '">' + c.value + '</div>' +
        '<div class="k-foot">' + c.foot + '</div>' +
        '</div>';
    }).join('');
  }

  /* -------------------------------------------------------------- rendering */

  function renderAll(agg) {
    renderKPIs(agg);
    drawTrend(document.getElementById('c-trend'), agg);
    drawCatSub(document.getElementById('c-catsub'), agg);
    drawDiscount(document.getElementById('c-disc'), agg);
    drawMap(document.getElementById('c-map'), agg);
    drawStates(document.getElementById('c-states'), agg);
    drawHeat(document.getElementById('c-heat'), agg);
    drawYear(document.getElementById('c-year'), agg);
  }

  /* ----------------------------------------------------------------- state */

  var RECORDS = null;
  var FILTERS = { year: 'All', region: 'All', category: 'All', segment: 'All' };
  var BUILT_AT = null;

  function uniqueSorted(recs, key) {
    var s = new Set();
    recs.forEach(function (r) { s.add(r[key]); });
    return Array.from(s).sort();
  }

  function fillSlicers(recs) {
    [['f-year', 'year'], ['f-region', 'region'], ['f-category', 'category'], ['f-segment', 'segment']]
      .forEach(function (pair) {
        var sel = document.getElementById(pair[0]);
        var cur = FILTERS[pair[1]];
        var opts = ['All'].concat(uniqueSorted(recs, pair[1]));
        sel.innerHTML = opts.map(function (o) {
          return '<option value="' + o + '"' + (o === cur ? ' selected' : '') + '>' +
            (o === 'All' ? 'All' : o) + '</option>';
        }).join('');
      });
  }

  function scopeText(agg) {
    var parts = [];
    ['year', 'region', 'category', 'segment'].forEach(function (k) {
      if (FILTERS[k] !== 'All') parts.push(k.charAt(0).toUpperCase() + k.slice(1) + ' = ' + FILTERS[k]);
    });
    var dot = document.getElementById('scope-dot');
    var el2 = document.getElementById('scope-text');
    if (!parts.length) {
      el2.textContent = 'All data in scope · ' + num(agg.lineItems) + ' line items';
      dot.className = 'dot';
    } else {
      el2.textContent = 'Filtered · ' + parts.join(' · ') + ' · ' + num(agg.lineItems) + ' line items';
      dot.className = 'dot dirty';
    }
    var hint = document.getElementById('trend-hint');
    if (hint) hint.textContent = 'monthly · ' + agg.monthKeys.length + ' months';
  }

  function update(recs) {
    var agg = aggregate(recs, FILTERS);
    renderAll(agg);
    scopeText(agg);
    return agg;
  }

  /* --------------------------------------------------- integrity vs python */

  function checkIntegrity(agg) {
    var host = document.getElementById('integrity');
    var ref = window.__REF__;
    if (!ref) { host.textContent = 'reference aggregates unavailable'; return; }
    var checks = [
      ['sales', agg.sales, ref.sales, 0.01],
      ['profit', agg.profit, ref.profit, 0.01],
      ['orders', agg.orderCount, ref.orders, 0],
      ['margin', agg.margin, ref.margin, 1e-6],
      ['line items', agg.lineItems, ref.lineItems, 0]
    ];
    var pass = 0;
    checks.forEach(function (c) { if (Math.abs(c[1] - c[2]) <= c[3]) pass++; });
    if (pass === checks.length) {
      host.innerHTML = '<span style="color:#15803d;font-weight:600">✓ ' + pass + '/' + checks.length +
        ' figures match the pandas reference</span> <span style="color:#cbd5e1">·</span> recomputed from CSV in-browser';
    } else {
      var bad = checks.filter(function (c) { return Math.abs(c[1] - c[2]) > c[3]; })
        .map(function (c) { return c[0] + ' js=' + c[1] + ' py=' + c[2]; }).join(', ');
      host.innerHTML = '<span style="color:#dc2626;font-weight:600">✗ mismatch: ' + bad + '</span>';
    }
  }

  /* ------------------------------------------------------------------ boot */

  function boot(rawText, now) {
    RECORDS = toRecords(rawText);
    BUILT_AT = now || new Date();
    fillSlicers(RECORDS);
    var agg = update(RECORDS);
    checkIntegrity(agg);
    var st = document.getElementById('stamp-time');
    if (st && !st.dataset.fixed) {
      st.textContent = BUILT_AT.toLocaleString('en-GB', {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    }
    return agg;
  }

  function rebuild() {
    var btn = document.getElementById('rebuild');
    var t0 = performance.now();
    btn.disabled = true;
    var label = btn.innerHTML;
    btn.innerHTML = 'Rebuilding…';
    setTimeout(function () {
      try {
        var raw = document.getElementById('raw-csv').textContent;
        boot(raw, new Date());
        var ms = Math.round(performance.now() - t0);
        document.getElementById('scope-text').textContent =
          'Rebuilt ' + RECORDS.length.toLocaleString('en-US') + ' rows in ' + ms + ' ms · ' + new Date().toLocaleTimeString('en-GB');
        var dot = document.getElementById('scope-dot');
        dot.className = 'dot';
        btn.innerHTML = '✓ Rebuilt';
        setTimeout(function () { btn.innerHTML = label; btn.disabled = false; }, 900);
      } catch (e) {
        btn.innerHTML = 'Rebuild failed';
        document.getElementById('integrity').textContent = 'rebuild error: ' + e.message;
        btn.disabled = false;
      }
    }, 16);
  }

  function wire() {
    ['f-year', 'f-region', 'f-category', 'f-segment'].forEach(function (id) {
      var key = id.slice(2);
      document.getElementById(id).addEventListener('change', function (e) {
        FILTERS[key] = e.target.value;
        update(RECORDS);
      });
    });
    document.getElementById('clear').addEventListener('click', function () {
      FILTERS = { year: 'All', region: 'All', category: 'All', segment: 'All' };
      fillSlicers(RECORDS);
      update(RECORDS);
    });
    document.getElementById('rebuild').addEventListener('click', rebuild);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'r' && (e.ctrlKey || e.metaKey) && e.shiftKey) { e.preventDefault(); rebuild(); }
    });
  }

  function start() {
    var node = document.getElementById('raw-csv');
    if (!node) { document.getElementById('integrity').textContent = 'embedded data missing'; return; }
    var st = document.getElementById('stamp-time');
    if (st && st.textContent.trim() && st.textContent.indexOf('__') !== 0) st.dataset.fixed = '1';
    boot(node.textContent, null);
    wire();
    window.__AGG__ = function () { return aggregate(RECORDS, FILTERS); };
    window.__READY__ = true;
    // headless self-test: dashboard.html?rebuild=1 exercises the button's handler
    if (/[?&]rebuild(=|&|$)/.test(location.search)) setTimeout(rebuild, 40);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
