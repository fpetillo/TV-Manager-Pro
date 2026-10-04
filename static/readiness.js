;(() => {
  let fingerprint = '';
  window.renderInstallationChecks = data => {
    const box = document.getElementById('installationChecks');
    fingerprint = data.fingerprint;
    box.innerHTML = `<p><strong>${esc(data.passed)} of ${esc(data.total)} checks passed</strong> · Checked ${esc(new Date(data.checked_at).toLocaleString())}</p>` + data.checks.map(item => {
      const state = item.status === 'passed' ? (item.source === 'operator' ? 'Operator verified' : 'Passed') : item.status === 'unverified' ? 'Unverified' : 'Needs attention';
      const header = `<strong>${esc(item.title)}</strong> <span class="status-pill">${state}</span>`;
      const detail = `<p>${esc(item.detail)}</p><a class="btn secondary" href="${esc(item.href)}">Open ${item.source === 'operator' ? 'test' : 'correction'} page</a>`;
      if (item.source !== 'operator') return `<div class="result-card">${header}${detail}</div>`;
      return `<details class="result-card"><summary>${header}</summary>${detail}
        ${item.review ? `<p class="muted">Last recorded: ${esc(new Date(item.review.verified_at).toLocaleString())}${item.stale ? ' — Repeat verification after changes or expiry.' : ''}</p>` : ''}
        <form data-check="${esc(item.key)}"><label>Test performed and result<textarea name="evidence" rows="3" minlength="20" maxlength="2000" required>${esc(item.review?.evidence || '')}</textarea></label>
        <small>Record the episode, client or backup tested. Keep passwords and API keys out of these notes.</small>
        <label class="checkline"><input type="checkbox" name="confirmed" required> I performed this verification on this installation and it passed.</label>
        <div class="actions"><button type="submit" class="blue">Record Verification</button>${item.review ? '<button type="button" data-clear class="secondary">Clear Verification</button>' : ''}</div><p role="status" data-message></p></form></details>`;
    }).join('');
    box.querySelectorAll('form[data-check]').forEach(form => {
      async function submit(clear) {
        const message = form.querySelector('[data-message]');
        const buttons = form.querySelectorAll('button'); buttons.forEach(b => b.disabled = true);
        try {
          const response = await fetch('/api/readiness/' + encodeURIComponent(form.dataset.check) + '/verify', {
            method: clear ? 'DELETE' : 'POST', headers: {'Content-Type':'application/json'},
            ...(clear ? {} : {body:JSON.stringify({fingerprint, evidence:form.elements.evidence.value, confirmed:form.elements.confirmed.checked})})
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Could not record verification.');
          await loadLaunchpad();
        } catch (error) {message.textContent = error.message;}
        finally {buttons.forEach(b => b.disabled = false);}
      }
      form.addEventListener('submit', event => {event.preventDefault(); submit(false);});
      form.querySelector('[data-clear]')?.addEventListener('click', () => submit(true));
    });
  };
})();
