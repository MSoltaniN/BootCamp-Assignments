// Runs inside the iCourse page. Decodes a base64+gzip payload and fills fields.
// Used via page.evaluate(FILLER_SOURCE, {...}) from the MCP evaluate channel.
(() => {
  window.__fillSection = async function (b64, dryRun) {
    // base64 -> bytes
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);

    // gzip -> text
    const stream = new Blob([bytes]).stream().pipeThrough(
      new DecompressionStream('gzip')
    );
    const payload = JSON.parse(await new Response(stream).text());

    const setText = (el, value) => {
      const proto = el.tagName === 'TEXTAREA'
        ? window.HTMLTextAreaElement.prototype
        : window.HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, String(value));
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const out = { filled: 0, skipped: 0, errors: [], perQuestion: {} };

    for (const [qid, fields] of Object.entries(payload)) {
      const article = document.getElementById('q-' + qid);
      if (!article) { out.errors.push(qid + ':article-missing'); continue; }

      let done = 0;
      for (const [index, spec] of Object.entries(fields)) {
        const answer = spec.answer;
        if (answer === null || answer === undefined || answer === '') {
          out.skipped += 1;
          continue;
        }

        if (spec.kind === 'choice') {
          const group = document.getElementById(spec.field_id + '-l');
          const scope = group ? group.parentElement : article;
          const buttons = scope
            ? [...scope.querySelectorAll('[role="radio"]')]
            : [];
          const wanted = String(answer).trim();
          const button = buttons.find(b => b.textContent.trim() === wanted);
          if (!button) {
            out.errors.push(spec.field_id + ':no-option:' + wanted);
            continue;
          }
          if (!dryRun) button.click();
          done += 1;
          continue;
        }

        const el = document.getElementById(spec.field_id);
        if (!el) { out.errors.push(spec.field_id + ':no-input'); continue; }
        if (!dryRun) setText(el, answer);
        done += 1;
      }

      out.filled += done;
      out.perQuestion[qid] = {
        done,
        total: Object.keys(fields).length,
        answered: article.getAttribute('data-answered'),
      };
    }

    out.bar = (document.querySelector('[class*="AssignmentForm_barText"]') || {}).textContent;
    return out;
  };
  return 'ready';
})();
