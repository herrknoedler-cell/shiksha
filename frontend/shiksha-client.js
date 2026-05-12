/* =========================================================
   ShikshaClient — Frontend-Library für api.shiksha.world

   Gemeinsam genutzt von:
     - presence_switch.html  (Auth-Gate)
     - mira_app.html         (Tagesausklang + Sessions + Memory)
     - krummelus_kennenlernen_v2.html (Kennenlerngespräch)

   Lädt @simplewebauthn/browser von CDN als ES-Module.

   Usage:
     import { ShikshaClient } from './shiksha-client.js';
     const client = new ShikshaClient('https://api.shiksha.world');

     // Login
     await client.loginWithPasskey('krummelus_mira');

     // Chat (Streaming)
     for await (const delta of client.chatStream({
       user_message: 'Heute war...',
       persona: 'tagesausklang'
     })) {
       if (delta.delta) appendToUI(delta.delta);
       if (delta.done)  finalize(delta);
     }
   ========================================================= */

import {
  startAuthentication,
  startRegistration,
  browserSupportsWebAuthn,
} from 'https://cdn.jsdelivr.net/npm/@simplewebauthn/browser@10.0.0/dist/bundle/index.min.js';

const TOKEN_KEY = 'shiksha-token';
const OPERATOR_KEY = 'shiksha-operator';

export class ShikshaClient {
  /**
   * @param {string} baseUrl  z.B. "https://api.shiksha.world"
   */
  constructor(baseUrl = 'https://api.shiksha.world') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  // -----------------------------------------------------------------
  // TOKEN-MANAGEMENT
  // -----------------------------------------------------------------

  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  setToken(token, operatorMeta = null) {
    localStorage.setItem(TOKEN_KEY, token);
    if (operatorMeta) {
      localStorage.setItem(OPERATOR_KEY, JSON.stringify(operatorMeta));
    }
  }

  clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(OPERATOR_KEY);
  }

  getOperatorMeta() {
    try {
      const raw = localStorage.getItem(OPERATOR_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  hasValidToken() {
    return !!this.getToken();
  }

  // -----------------------------------------------------------------
  // HTTP HELPERS
  // -----------------------------------------------------------------

  _headers(extra = {}) {
    const token = this.getToken();
    const headers = { 'Content-Type': 'application/json', ...extra };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async _fetch(path, options = {}) {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: this._headers(options.headers),
    });

    if (res.status === 401) {
      // Token ist tot — Aufrufer entscheidet ob er reagiert
      this.clearToken();
      throw new ShikshaAuthError('Token invalid or expired');
    }

    if (res.status === 429) {
      const body = await res.json().catch(() => ({}));
      throw new ShikshaRateLimitError(
        body.detail || 'Tageslimit erreicht.',
        body.reset_at,
      );
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ShikshaApiError(
        body.detail || `HTTP ${res.status}`,
        res.status,
        body,
      );
    }

    if (res.status === 204) return null;
    return res.json();
  }

  // -----------------------------------------------------------------
  // AUTH — WebAuthn / Passkey
  // -----------------------------------------------------------------

  /**
   * Passkey-Login für einen bekannten Operator.
   * Nutzt WebAuthn — Browser zeigt Face ID / Touch ID / Windows Hello.
   *
   * Wenn der Operator noch keinen Passkey hat (Erst-Setup-Fall),
   * fällt der Aufruf automatisch auf registerPasskey zurück — vorausgesetzt
   * der Backend-Check erlaubt es (keine existierenden Credentials).
   */
  async loginWithPasskey(operatorId) {
    if (!browserSupportsWebAuthn()) {
      throw new ShikshaApiError('WebAuthn nicht unterstützt in diesem Browser', 0);
    }

    // 1. Challenge holen
    const beginRes = await fetch(`${this.baseUrl}/api/v1/auth/login/begin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator_id: operatorId }),
    });

    // Erst-Setup-Fall: Backend sagt "No passkey registered"
    // → automatisch zu register wechseln, ohne Token (Erst-Setup-Pfad erlaubt)
    if (beginRes.status === 400) {
      const body = await beginRes.json().catch(() => ({}));
      const detail = (body.detail || '').toLowerCase();
      if (detail.includes('no passkey') || detail.includes('register/begin')) {
        // Auto-Fallback: erstmaliges Setup
        return await this.registerPasskey(operatorId);
      }
      throw new ShikshaApiError(body.detail || 'login/begin failed', beginRes.status, body);
    }

    if (!beginRes.ok) {
      const body = await beginRes.json().catch(() => ({}));
      throw new ShikshaApiError(body.detail || 'login/begin failed', beginRes.status, body);
    }
    const { options } = await beginRes.json();

    // 2. Browser-Ceremony
    let credential;
    try {
      credential = await startAuthentication({ optionsJSON: options });
    } catch (err) {
      throw new ShikshaApiError(`Passkey-Authentifizierung abgebrochen: ${err.message}`, 0);
    }

    // 3. Verifikation
    const finishRes = await fetch(`${this.baseUrl}/api/v1/auth/login/finish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator_id: operatorId, credential }),
    });
    if (!finishRes.ok) {
      const body = await finishRes.json().catch(() => ({}));
      throw new ShikshaApiError(body.detail || 'login/finish failed', finishRes.status, body);
    }
    const tokenData = await finishRes.json();

    this.setToken(tokenData.token, {
      operator_id:  tokenData.operator_id,
      display_name: tokenData.display_name,
      role:         tokenData.role,
      edition:      tokenData.edition,
    });

    return tokenData;
  }

  /**
   * Passkey-Registrierung. Operator muss schon in der DB sein
   * (per Seed oder Setup-Token-Flow).
   *
   * @param {string} operatorId
   * @param {string|null} setupToken — required wenn Operator schon
   *     einen Passkey hat. Bei Erst-Setup: optional.
   */
  async registerPasskey(operatorId, setupToken = null) {
    if (!browserSupportsWebAuthn()) {
      throw new ShikshaApiError('WebAuthn nicht unterstützt', 0);
    }

    const tokenParam = setupToken ? `?setup_token=${encodeURIComponent(setupToken)}` : '';

    const beginRes = await fetch(
      `${this.baseUrl}/api/v1/auth/register/begin/${encodeURIComponent(operatorId)}${tokenParam}`,
      { method: 'POST' },
    );
    if (!beginRes.ok) {
      const body = await beginRes.json().catch(() => ({}));
      throw new ShikshaApiError(body.detail || 'register/begin failed', beginRes.status, body);
    }
    const { options } = await beginRes.json();

    let credential;
    try {
      credential = await startRegistration({ optionsJSON: options });
    } catch (err) {
      throw new ShikshaApiError(`Passkey-Registrierung abgebrochen: ${err.message}`, 0);
    }

    const finishRes = await fetch(
      `${this.baseUrl}/api/v1/auth/register/finish${tokenParam}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operator_id: operatorId, credential }),
      },
    );
    if (!finishRes.ok) {
      const body = await finishRes.json().catch(() => ({}));
      throw new ShikshaApiError(body.detail || 'register/finish failed', finishRes.status, body);
    }
    const tokenData = await finishRes.json();

    this.setToken(tokenData.token, {
      operator_id:  tokenData.operator_id,
      display_name: tokenData.display_name,
      role:         tokenData.role,
      edition:      tokenData.edition,
    });

    return tokenData;
  }

  async me() {
    return this._fetch('/api/v1/auth/me');
  }

  async refresh() {
    const data = await this._fetch('/api/v1/auth/refresh', { method: 'POST' });
    this.setToken(data.token);
    return data;
  }

  logout() {
    this.clearToken();
  }

  // -----------------------------------------------------------------
  // CHAT
  // -----------------------------------------------------------------

  /**
   * Block-Antwort. Liefert {session_id, shiksha_response, mode, tokens_used}.
   */
  async chatRespond({ session_id = null, user_message, persona = 'tagesausklang' }) {
    return this._fetch('/api/v1/chat/respond', {
      method: 'POST',
      body: JSON.stringify({ session_id, user_message, persona }),
    });
  }

  /**
   * Streaming-Antwort via SSE.
   * Async-Generator yielded:
   *   {session_id: "..."}       — am Anfang
   *   {delta: "Wort"}            — pro Chunk
   *   {done: true, mode, tokens_used} — am Ende
   */
  async *chatStream({ session_id = null, user_message, persona = 'tagesausklang' }) {
    const token = this.getToken();
    if (!token) throw new ShikshaAuthError('Not authenticated');

    const res = await fetch(`${this.baseUrl}/api/v1/chat/stream`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type':  'application/json',
        'Accept':        'text/event-stream',
      },
      body: JSON.stringify({ session_id, user_message, persona }),
    });

    if (res.status === 401) {
      this.clearToken();
      throw new ShikshaAuthError('Token invalid or expired');
    }
    if (res.status === 429) {
      const body = await res.json().catch(() => ({}));
      throw new ShikshaRateLimitError(body.detail, body.reset_at);
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ShikshaApiError(body.detail || `HTTP ${res.status}`, res.status, body);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE-Parse: Events sind durch \n\n getrennt
        let nl;
        while ((nl = buffer.indexOf('\n\n')) !== -1) {
          const eventBlock = buffer.slice(0, nl);
          buffer = buffer.slice(nl + 2);

          // Eine Event-Zeile beginnt mit "data: "
          const dataLines = eventBlock
            .split('\n')
            .filter(l => l.startsWith('data: '))
            .map(l => l.slice(6));
          if (!dataLines.length) continue;

          const dataStr = dataLines.join('\n');
          try {
            yield JSON.parse(dataStr);
          } catch (err) {
            console.warn('SSE-Parse-Fehler', err, dataStr);
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Session schließen — triggert Insights-Extraction.
   */
  async closeSession(sessionId, { extractInsights = true } = {}) {
    return this._fetch(
      `/api/v1/chat/close/${encodeURIComponent(sessionId)}?extract_insights=${extractInsights}`,
      { method: 'POST' },
    );
  }

  // -----------------------------------------------------------------
  // SESSIONS
  // -----------------------------------------------------------------

  async listSessions(filters = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') {
        params.append(k, v);
      }
    });
    const qs = params.toString();
    return this._fetch(`/api/v1/sessions${qs ? '?' + qs : ''}`);
  }

  async getSession(sessionId) {
    return this._fetch(`/api/v1/sessions/${encodeURIComponent(sessionId)}`);
  }

  // -----------------------------------------------------------------
  // MEMORY
  // -----------------------------------------------------------------

  async listMemory({ limit = 50, offset = 0 } = {}) {
    return this._fetch(`/api/v1/memory?limit=${limit}&offset=${offset}`);
  }

  async memoryCount() {
    return this._fetch('/api/v1/memory/count');
  }

  async addMemory(text, sourceSessionId = null) {
    return this._fetch('/api/v1/memory', {
      method: 'POST',
      body: JSON.stringify({ text, source_session_id: sourceSessionId }),
    });
  }

  async patchMemory(id, text) {
    return this._fetch(`/api/v1/memory/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ text }),
    });
  }

  async deleteMemory(id) {
    return this._fetch(`/api/v1/memory/${id}`, { method: 'DELETE' });
  }

  // -----------------------------------------------------------------
  // META
  // -----------------------------------------------------------------

  async health() {
    return this._fetch('/health');
  }
}

// -----------------------------------------------------------------
// Error-Typen
// -----------------------------------------------------------------

export class ShikshaApiError extends Error {
  constructor(message, status = 0, body = null) {
    super(message);
    this.name = 'ShikshaApiError';
    this.status = status;
    this.body = body;
  }
}

export class ShikshaAuthError extends ShikshaApiError {
  constructor(message) {
    super(message, 401);
    this.name = 'ShikshaAuthError';
  }
}

export class ShikshaRateLimitError extends ShikshaApiError {
  constructor(message, resetAt) {
    super(message, 429);
    this.name = 'ShikshaRateLimitError';
    this.resetAt = resetAt;
  }
}

// -----------------------------------------------------------------
// Convenience: Default-Instanz bei der Default-API-URL
// -----------------------------------------------------------------

export const defaultClient = new ShikshaClient();
