/* Presentation controls are separate from map data and account permissions. */
(() => {
  const workspace = document.querySelector('.workspace');
  const toolbar = document.createElement('nav');
  toolbar.className = 'workspace-toolbar';
  toolbar.setAttribute('aria-label', 'Workspace panels and map controls');
  toolbar.innerHTML = `<div class="workspace-views">
    <button type="button" class="workspace-view" data-panel="atlas" aria-controls="atlasPanel" aria-pressed="true"><svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="3" width="14" height="14" rx="2"/><path d="M8 3v14"/></svg>Atlas</button>
    <button type="button" class="workspace-view" data-panel="map" aria-controls="mapStage" aria-pressed="false"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7"/><ellipse cx="10" cy="10" rx="3" ry="7"/><path d="M3 10h14"/></svg>Map</button>
    <button type="button" class="workspace-view" data-panel="inspector" aria-controls="inspectorPanel" aria-pressed="true"><svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="3" width="14" height="14" rx="2"/><path d="M12 3v14"/></svg>Inspector</button>
  </div><div class="map-tools"></div>`;
  workspace.before(toolbar);
  const inspector = document.querySelector('.right-panel');
  // Keep optional lookup tools available without pushing GPS results below the fold.
  document.querySelectorAll('.resource-finder, .favorites-panel').forEach(section => {
    const disclosure = document.createElement('details');
    disclosure.className = `${section.className} atlas-disclosure`;
    disclosure.id = section.id;
    const heading = section.querySelector('.panel-heading');
    const summary = document.createElement('summary');
    summary.className = 'panel-heading';
    summary.append(...heading.childNodes);
    heading.replaceWith(summary);
    disclosure.append(...section.childNodes);
    section.replaceWith(disclosure);
  });
  const grouping = document.querySelector('.gps-group-toggle');
  if (grouping) document.getElementById('resourceFinder').append(grouping);
  const sectors = document.getElementById('sectorPicker');
  const sectorHeading = sectors.previousElementSibling;
  const sectorDisclosure = document.createElement('details');
  sectorDisclosure.className = 'atlas-disclosure sector-disclosure';
  const sectorSummary = document.createElement('summary');
  sectorSummary.className = 'panel-heading';
  sectorSummary.append(...sectorHeading.childNodes);
  sectorHeading.replaceWith(sectorDisclosure);
  sectorDisclosure.append(sectorSummary, sectors);
  document.querySelector('.left-panel').id = 'atlasPanel';
  inspector.id = 'inspectorPanel';
  const position = document.querySelector('.position-card');
  const activity = document.querySelector('.activity-card');
  inspector.append(position);
  if (activity) inspector.append(activity);
  const mapTools = toolbar.querySelector('.map-tools');
  ['centerView', 'resetView', 'toggleMapLayers'].forEach(id => mapTools.append(document.getElementById(id)));
  document.getElementById('centerView').textContent = '◎ Center';
  document.getElementById('resetView').textContent = '↺ Reset';
  document.getElementById('zoomIn').setAttribute('aria-label', 'Zoom in');
  document.getElementById('zoomOut').setAttribute('aria-label', 'Zoom out');

  const compact = matchMedia('(max-width: 1000px)');
  let left = true, right = true, mobilePanel = 'map';
  function renderPanels() {
    workspace.dataset.left = String(left);
    workspace.dataset.right = String(right);
    workspace.dataset.mobile = mobilePanel;
    toolbar.querySelectorAll('[data-panel]').forEach(button => {
      const panel = button.dataset.panel;
      const pressed = compact.matches ? mobilePanel === panel : panel === 'atlas' ? left : panel === 'inspector' ? right : !left && !right;
      button.setAttribute('aria-pressed', String(pressed));
      button.title = compact.matches ? `Show ${panel}` : panel === 'map' ? 'Expand map / restore panels' : `Toggle ${panel}`;
    });
    requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  }
  toolbar.addEventListener('click', event => {
    const button = event.target.closest('[data-panel]');
    if (!button) return;
    const panel = button.dataset.panel;
    if (compact.matches) mobilePanel = panel;
    else if (panel === 'atlas') left = !left;
    else if (panel === 'inspector') right = !right;
    else { const expand = left || right; left = !expand; right = !expand; }
    renderPanels();
  });
  compact.addEventListener('change', renderPanels);
  renderPanels();

  // Keyboard search and modal focus handling work without changing feature handlers.
  document.addEventListener('keydown', event => {
    const editing = event.target.closest('input, textarea, select, [contenteditable="true"]');
    const modal = document.querySelector('.modal:not(.hidden)');
    if (event.key === '/' && !editing && !modal) {
      event.preventDefault(); left = true; mobilePanel = 'atlas'; renderPanels();
      document.getElementById('search').focus();
    }
    if (!modal) return;
    if (event.key === 'Escape') modal.querySelector('.modal-close')?.click();
    if (event.key !== 'Tab') return;
    const controls = [...modal.querySelectorAll('button, input, textarea, select, [tabindex="0"]')].filter(el => !el.disabled && el.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (!first) return;
    if (event.shiftKey && (document.activeElement === first || !modal.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || !modal.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
  });
  let lastDialogTrigger;
  document.addEventListener('click', event => {
    if (!event.target.closest('.modal')) lastDialogTrigger = event.target.closest('button, input, select, [tabindex]');
  }, true);
  document.querySelectorAll('.modal').forEach(modal => {
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    const heading = modal.querySelector('h2');
    if (heading) { heading.id ||= `${modal.id}Title`; modal.setAttribute('aria-labelledby', heading.id); }
    let wasOpen = false, previousFocus;
    const update = () => {
      const open = !modal.classList.contains('hidden');
      document.querySelector('.app-shell').inert = Boolean(document.querySelector('.modal:not(.hidden)'));
      if (open && !wasOpen) {
        previousFocus = document.activeElement === document.body || modal.contains(document.activeElement) ? lastDialogTrigger : document.activeElement;
        requestAnimationFrame(() => modal.querySelector('input:not([type="hidden"]), textarea, select, button')?.focus());
      } else if (!open && wasOpen && previousFocus?.isConnected) previousFocus.focus();
      wasOpen = open;
    };
    new MutationObserver(update).observe(modal, {attributes: true, attributeFilter: ['class']});
    update();
  });
  // Replace the legacy constant "100%" with the actual bridge status.
  const status = document.getElementById('datasetStatus');
  const sync = document.querySelector('.telemetry-grid .green');
  const live = document.querySelector('.right-panel > .panel-heading .live');
  function updateConnection() {
    const connected = status.textContent === 'MYSQL CONNECTED';
    document.querySelector('.system-status').dataset.connected = String(connected);
    if (sync) sync.textContent = connected ? 'Online' : 'Offline';
    if (live) { live.textContent = connected ? 'CONNECTED' : 'OFFLINE'; live.style.color = connected ? 'var(--cyan)' : 'var(--muted)'; }
  }
  new MutationObserver(updateConnection).observe(status, {childList: true, characterData: true, subtree: true});
  updateConnection();
})();
