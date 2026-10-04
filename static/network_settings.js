;(() => {
  const byId = id => document.getElementById(id);
  function selectTab() {
    const name = location.hash.slice(1);
    const button = [...document.querySelectorAll('.settings-tab')].find(b => b.dataset.view === name);
    if (button) button.click();
  }
  document.querySelectorAll('.settings-tab').forEach(button => button.addEventListener('click', () => {
    history.replaceState(null, '', '#' + button.dataset.view);
  }));
  window.addEventListener('hashchange', selectTab);
  selectTab();

  async function request(method = 'GET', body) {
    const response = await fetch('/api/settings/network', {
      method, headers: {'Content-Type': 'application/json'},
      ...(body ? {body: JSON.stringify(body)} : {})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not load network settings.');
    return result;
  }
  function render(data) {
    byId('listenHost').value = data.config.host;
    byId('listenPort').value = data.config.port;
    byId('localAddresses').replaceChildren(...data.addresses.map(address => {
      const option = document.createElement('option'); option.value = address; return option;
    }));
    byId('networkStatus').textContent = `Current listener: ${data.active.host}:${data.active.port}. ` +
      (data.restart_required ? `Restart required to use ${data.config.host}:${data.config.port}.` : 'Saved settings are active.') +
      (data.override ? ' A temporary startup override is active.' : '');
    byId('saveNetwork').disabled = data.override;
  }
  request().then(render).catch(error => {byId('networkStatus').textContent = error.message;});
  byId('saveNetwork').addEventListener('click', async () => {
    const message = byId('networkMessage'), button = byId('saveNetwork');
    button.disabled = true;
    try {
      const data = await request('POST', {host: byId('listenHost').value, port: byId('listenPort').value});
      render(data);
      message.className = 'notice good';
      message.textContent = data.restart_required ? 'Saved. Restart TV Manager, then open ' +
        (data.url || `http://your-server-IP:${data.config.port}`) + '. This window stays connected until the restart.' : 'Saved. These network settings are already active.';
    } catch (error) {
      message.className = 'notice warn'; message.textContent = error.message;
    } finally {button.disabled = false;}
  });
})();
