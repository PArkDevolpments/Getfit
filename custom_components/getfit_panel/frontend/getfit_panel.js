/* Getfit Home Assistant full-canvas panel.
   The parent owns Home Assistant/Supervisor credentials. The Getfit child remains
   behind Supervisor Ingress and receives only the normal ingress identity headers. */

const PANEL_TAG = 'getfit-full-canvas-panel';
const DEFAULT_ADDON_SLUG = 'getfit';

function setIngressCookie(session) {
  document.cookie = `ingress_session=${session};path=/api/hassio_ingress/;SameSite=Strict${location.protocol === 'https:' ? ';Secure' : ''}`;
}

class GetfitFullCanvasPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._panel = null;
    this._narrow = false;
    this._route = null;
    this._frame = null;
    this._keepAlive = null;
    this._loading = false;
    this._messageHandler = (event) => this._handleChildMessage(event);
    this.attachShadow({mode: 'open'});
  }

  set hass(value) {
    this._hass = value || null;
    void this._ensureFrame();
  }
  get hass() { return this._hass; }

  set panel(value) {
    this._panel = value || null;
    void this._ensureFrame();
  }
  get panel() { return this._panel; }

  set narrow(value) {
    this._narrow = Boolean(value);
    this._sendProperties();
  }
  get narrow() { return this._narrow; }

  set route(value) {
    this._route = value || null;
    this._sendProperties();
  }
  get route() { return this._route; }

  connectedCallback() {
    window.addEventListener('message', this._messageHandler);
    this._renderStatus('Opening Getfit…');
    void this._ensureFrame();
  }

  disconnectedCallback() {
    window.removeEventListener('message', this._messageHandler);
    if (this._keepAlive) window.clearInterval(this._keepAlive);
    this._keepAlive = null;
  }

  _addonSlug() {
    return String(this._panel?.config?.addon_slug || DEFAULT_ADDON_SLUG);
  }

  _renderStatus(message, error = false) {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display:block;
          width:100%;
          height:100%;
          min-height:100%;
          background:#06100e;
          color:#f0f4ef;
          font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
        }
        .status {
          box-sizing:border-box;
          min-height:100%;
          display:grid;
          place-items:center;
          padding:
            max(20px, var(--safe-area-inset-top, 0px))
            20px
            max(20px, var(--safe-area-inset-bottom, 0px));
          text-align:center;
          background:
            radial-gradient(circle at 80% 0%, rgba(54,201,133,.10), transparent 28rem),
            #06100e;
        }
        .status strong { display:block; font-size:1.05rem; }
        .status span { display:block; margin-top:6px; color:#98a69f; font-size:.78rem; }
        .status.error strong { color:#ffb8c0; }
      </style>
      <div class="status ${error ? 'error' : ''}">
        <div><strong>${message}</strong><span>${error ? 'The Getfit app and existing data are unchanged.' : 'Secure Home Assistant ingress'}</span></div>
      </div>
    `;
  }

  async _createSession() {
    const response = await this._hass.callWS({
      type: 'supervisor/api',
      endpoint: '/ingress/session',
      method: 'post',
    });
    if (!response?.session) throw new Error('INGRESS_SESSION_UNAVAILABLE');
    setIngressCookie(response.session);
    return response.session;
  }

  async _ensureFrame() {
    if (!this.isConnected || !this._hass || this._frame || this._loading) return;
    this._loading = true;
    try {
      const slug = this._addonSlug();
      const addon = await this._hass.callWS({
        type: 'supervisor/api',
        endpoint: `/addons/${slug}/info`,
        method: 'get',
      });
      if (!addon?.installed) throw new Error('GETFIT_APP_NOT_INSTALLED');
      if (addon.state !== 'started') throw new Error('GETFIT_APP_NOT_RUNNING');
      if (!addon.ingress_url) throw new Error('GETFIT_INGRESS_UNAVAILABLE');

      let session = await this._createSession();

      this.shadowRoot.innerHTML = `
        <style>
          :host {
            display:block;
            width:100%;
            height:100%;
            min-height:100%;
            overflow:hidden;
            background:#06100e;
          }
          iframe {
            display:block;
            width:100%;
            height:100%;
            min-height:100%;
            border:0;
            background:#06100e;
          }
        </style>
        <iframe title="Getfit" allow="fullscreen"></iframe>
      `;
      this._frame = this.shadowRoot.querySelector('iframe');
      this._frame.src = addon.ingress_url;

      if (this._keepAlive) window.clearInterval(this._keepAlive);
      this._keepAlive = window.setInterval(async () => {
        try {
          await this._hass.callWS({
            type: 'supervisor/api',
            endpoint: '/ingress/validate_session',
            method: 'post',
            data: {session},
          });
        } catch (_) {
          try {
            session = await this._createSession();
            this._frame?.contentWindow?.location.reload();
          } catch (_) {
            this._renderStatus('Getfit ingress session expired', true);
          }
        }
      }, 60000);
    } catch (error) {
      const code = String(error?.message || error || 'GETFIT_PANEL_UNAVAILABLE');
      const message = code === 'GETFIT_APP_NOT_RUNNING'
        ? 'Getfit is not running'
        : code === 'GETFIT_APP_NOT_INSTALLED'
          ? 'Getfit is not installed'
          : 'Getfit could not be opened';
      this._renderStatus(message, true);
    } finally {
      this._loading = false;
    }
  }

  _handleChildMessage(event) {
    if (!this._frame || event.source !== this._frame.contentWindow) return;
    if (!event.data || event.data.type !== 'home-assistant/subscribe-properties') return;
    this._sendProperties();
  }

  _safeAreaValue(name) {
    return getComputedStyle(this).getPropertyValue(name).trim();
  }

  _safeArea(primary, fallback = null) {
    return this._safeAreaValue(primary)
      || (fallback ? this._safeAreaValue(fallback) : '')
      || '0px';
  }

  _sendProperties() {
    if (!this._frame?.contentWindow) return;
    this._frame.contentWindow.postMessage({
      type: 'home-assistant/properties',
      host: 'getfit-full-canvas-panel',
      narrow: this._narrow,
      route: this._route?.path || '',
      safeAreaInsets: {
        top: this._safeArea('--safe-area-inset-top'),
        right: this._safeArea('--safe-area-content-inset-right', '--safe-area-inset-right'),
        bottom: this._safeArea('--safe-area-inset-bottom'),
        left: this._safeArea('--safe-area-content-inset-left', '--safe-area-inset-left'),
      },
    }, '*');
  }
}

if (!customElements.get(PANEL_TAG)) {
  customElements.define(PANEL_TAG, GetfitFullCanvasPanel);
}
