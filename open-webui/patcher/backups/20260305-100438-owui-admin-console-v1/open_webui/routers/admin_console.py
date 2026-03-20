from __future__ import annotations

import asyncio
import json
import os
import threading
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse

from open_webui.utils.auth import get_admin_user
from open_webui.utils.console_stream import get_console_stream


router = APIRouter()


_CONSOLE_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <button id="btnRestart" disabled>Restart OWUI</button>
  <title>Open WebUI Admin Console</title>
  <style>
    :root { color-scheme: dark; }
    body { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace; background:#0b1020; color:#e6e8ef; }
    header { padding: 12px 16px; background:#0f1633; border-bottom:1px solid #1f2a54; display:flex; gap:12px; align-items:center; }
    header h1 { font-size: 14px; margin: 0; opacity: .9; }
    header .spacer { flex: 1; }
    header button { background:#1f2a54; color:#e6e8ef; border:1px solid #2b3a75; padding: 6px 10px; border-radius: 8px; cursor:pointer; }
    #btnRestart { background:#6b1f1f; border-color:#9a2f2f; color:#ffeaea; }
    header button:disabled { opacity:.5; cursor: default; }
    main { padding: 12px 16px; }
    #status { margin: 8px 0 12px; opacity:.85; }
    #login { max-width: 420px; background:#0f1633; border:1px solid #1f2a54; border-radius: 12px; padding: 14px; }
    #login label { display:block; margin: 10px 0 6px; }
    #login input { width:100%; padding: 10px; border-radius: 10px; border:1px solid #2b3a75; background:#0b1020; color:#e6e8ef; }
    #login .row { display:flex; gap:10px; }
    #login .row > div { flex: 1; }
    #login .error { color:#ffb4b4; margin-top: 10px; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
    #logbox { background:#050815; border:1px solid #1f2a54; border-radius: 12px; padding: 12px; min-height: 60vh; max-height: 75vh; overflow:auto; }
    #hint { opacity:.7; font-size: 12px; margin-top: 10px; }
    #hosthint { opacity:.8; font-size: 12px; margin-top: 10px; line-height: 1.4; }
    code { background:#0b1020; border:1px solid #1f2a54; padding: 2px 6px; border-radius: 8px; }
  </style>
</head>
<body>
  <header>
    <div class=\"spacer\"></div>
    <button id=\"btnPause\" disabled>Pause</button>
    <button id=\"btnClear\" disabled>Clear</button>
  </header>
    <h1>Admin Console Stream</h1>
  <main>
    <div id=\"status\">Checking admin session…</div>
    <button id=\"btnRestart\" disabled>Restart OWUI</button>

    <div id=\"login\" style=\"display:none\">
      <div><strong>Admin login</strong></div>
      <div id=\"loginHint\" style=\"opacity:.8; margin-top:6px\">Sign in with an admin account to view server logs.</div>
      <div id=\"hosthint\">If you’re already logged in in another tab, make sure you opened this page on the same host (cookies don’t share between <code>localhost</code> and <code>127.0.0.1</code>).</div>
      <label>Email</label>
      <input id=\"email\" type=\"email\" autocomplete=\"username\" />
      <label>Password</label>
      <input id=\"password\" type=\"password\" autocomplete=\"current-password\" />
      <div style=\"margin-top:12px\">
        <button id=\"btnLogin\">Sign in</button>
        <button id=\"btnRetry\" type=\"button\">Retry stream</button>
      </div>
      <div id=\"loginError\" class=\"error\" style=\"display:none\"></div>
    </div>

    <div id=\"console\" style=\"display:none\">
      <div id=\"logbox\"><pre id=\"log\"></pre></div>
      <div id=\"hint\">Tip: leave this tab open to monitor logs in real time.</div>
    </div>
  </main>

  <!-- NOTE: JS is loaded as an external file to avoid CSP blocking inline scripts. -->
  <script src=\"/admin/console/app.js\"></script>
</body>
</html>"""


_CONSOLE_JS = r"""(function () {
      const statusEl = document.getElementById('status');
      const loginEl = document.getElementById('login');
      const consoleEl = document.getElementById('console');
      const logEl = document.getElementById('log');
      const logboxEl = document.getElementById('logbox');
      const btnRestart = document.getElementById('btnRestart');
      const btnPause = document.getElementById('btnPause');
      const btnClear = document.getElementById('btnClear');
      const btnLogin = document.getElementById('btnLogin');
      const btnRetry = document.getElementById('btnRetry');
      const loginError = document.getElementById('loginError');

      let paused = false;
      let es = null;
  let authToken = null;
  let fetchAbort = null;

      function setStatus(text) { statusEl.textContent = text; }
      function showLogin(errorText) {
        consoleEl.style.display = 'none';
        loginEl.style.display = 'block';
        btnRestart.disabled = true;
        btnPause.disabled = true;
        btnClear.disabled = true;
        if (errorText) {
          loginError.textContent = errorText;
          loginError.style.display = 'block';
        } else {
          loginError.style.display = 'none';
        }
      }
      function showConsole() {
        loginEl.style.display = 'none';
        consoleEl.style.display = 'block';
        btnRestart.disabled = false;
        btnPause.disabled = false;
        btnClear.disabled = false;
      }
      function appendLine(line) {
        if (paused) return;
        logEl.textContent += line + "\n";
        logboxEl.scrollTop = logboxEl.scrollHeight;
      }

      async function checkAdmin(timeoutMs = 4000) {
        const controller = new AbortController();
        const t = setTimeout(() => controller.abort(), timeoutMs);
        try {
          const headers = {};
          if (authToken) headers['Authorization'] = 'Bearer ' + authToken;
          const res = await fetch('/api/v1/auths/admin/config', {
            credentials: 'include',
            headers,
            signal: controller.signal,
            cache: 'no-store'
          });
          return res.ok;
        } catch {
          return false;
        } finally {
          clearTimeout(t);
        }
      }

      function stopFetchStream() {
        try { fetchAbort && fetchAbort.abort(); } catch {}
        fetchAbort = null;
      }

      function stopAllStreams() {
        stopFetchStream();
        if (es) {
          try { es.close(); } catch {}
          es = null;
        }
      }

      async function startFetchStream() {
        if (!authToken) {
          setStatus('Not signed in as admin.');
          showLogin('Please sign in with an admin account.');
          return;
        }

        stopAllStreams();

        fetchAbort = new AbortController();
        const signal = fetchAbort.signal;

        setStatus('Connecting to log stream…');
        try {
          const res = await fetch('/admin/console/stream', {
            method: 'GET',
            headers: { 'Authorization': 'Bearer ' + authToken },
            credentials: 'include',
            cache: 'no-store',
            signal
          });

          if (!res.ok) {
            if (res.status === 401 || res.status === 403) {
              setStatus('Not signed in as admin.');
              showLogin('Not authorized for admin log stream. Sign in with an admin account, then click Retry stream.');
              return;
            }
            const text = await res.text();
            setStatus('Stream error (' + res.status + ').');
            showLogin('Stream error: ' + text);
            return;
          }

          if (!res.body || !res.body.getReader) {
            setStatus('Streaming not supported in this browser.');
            showLogin('Please open this page in a modern browser (Chrome/Edge/Firefox).');
            return;
          }

          setStatus('Connected. Streaming logs…');
          showConsole();

          const reader = res.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let buffer = '';

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            while (true) {
              const idx = buffer.indexOf('\n\n');
              if (idx < 0) break;

              const chunk = buffer.slice(0, idx);
              buffer = buffer.slice(idx + 2);

              if (!chunk || chunk.startsWith(':')) continue; // keepalive/comment

              const lines = chunk.split('\n');
              for (const line of lines) {
                if (!line.startsWith('data:')) continue;
                const dataStr = line.slice(5).trim();
                try {
                  const payload = JSON.parse(dataStr);
                  if (payload && payload.line) appendLine(payload.line);
                } catch {
                  // ignore
                }
              }
            }
          }

          // If the stream ends normally, attempt reconnect.
          if (!signal.aborted) {
            setStatus('Stream disconnected. Reconnecting…');
            setTimeout(() => startFetchStream(), 1000);
          }
        } catch (e) {
          if (signal.aborted) return;
          const ok = await checkAdmin();
          if (!ok) {
            setStatus('Not signed in as admin.');
            showLogin('Not authorized for admin log stream. Sign in with an admin account, then click Retry stream.');
          } else {
            setStatus('Stream disconnected. Reconnecting…');
            setTimeout(() => startFetchStream(), 1000);
          }
        }
      }

      function startStream() {
        // If we have a token (e.g., cookies blocked / Secure cookies / VS Code Simple Browser),
        // prefer fetch streaming because EventSource cannot send Authorization headers.
        if (authToken) {
          startFetchStream();
          return;
        }

        if (typeof EventSource === 'undefined') {
          setStatus('This browser does not support EventSource/SSE.');
          showLogin('Please open this page in a modern browser (Chrome/Edge/Firefox).');
          return;
        }

        if (es) es.close();

        setStatus('Connecting to log stream…');
        let opened = false;
        const openTimeout = setTimeout(() => {
          if (!opened) {
            try { es && es.close(); } catch {}
            es = null;
            setStatus('Not signed in as admin.');
            showLogin('Stream connection timed out. If you are already logged in as admin in another tab, ensure this page uses the same host/port (localhost vs 127.0.0.1) then click Retry stream.');
          }
        }, 4000);

        es = new EventSource('/admin/console/stream');

        es.onopen = () => {
          opened = true;
          clearTimeout(openTimeout);
          setStatus('Connected. Streaming logs…');
          showConsole();
        };
        es.onmessage = (ev) => {
          try {
            const payload = JSON.parse(ev.data);
            if (payload && payload.line) appendLine(payload.line);
          } catch {
            // ignore
          }
        };
        es.onerror = async () => {
          clearTimeout(openTimeout);
          try { es && es.close(); } catch {}
          es = null;
          const ok = await checkAdmin();
          if (!ok) {
            setStatus('Not signed in as admin.');
            showLogin('Not authorized for admin log stream. Sign in with an admin account, then click Retry stream.');
          } else {
            setStatus('Stream disconnected. Reconnecting…');
            setTimeout(startStream, 1000);
          }
        };
      }

      btnPause.onclick = () => {
        paused = !paused;
        btnPause.textContent = paused ? 'Resume' : 'Pause';
      };
      btnClear.onclick = () => { logEl.textContent = ''; };
      btnRestart.onclick = async () => {
        const confirmed = window.confirm('Restart OWUI now? This will terminate the current process.');
        if (!confirmed) return;

        btnRestart.disabled = true;
        setStatus('Restarting OWUI…');
        try {
          const headers = {};
          if (authToken) headers['Authorization'] = 'Bearer ' + authToken;

          const res = await fetch('/admin/console/restart-owui', {
            method: 'POST',
            credentials: 'include',
            headers,
            cache: 'no-store'
          });

          if (!res.ok) {
            const text = await res.text();
            setStatus('Restart failed (' + res.status + ').');
            showLogin('Restart failed: ' + text);
            return;
          }

          stopAllStreams();
          setStatus('Restart signal sent. Waiting for OWUI to come back…');
          setTimeout(() => {
            startStream();
          }, 3000);
        } catch {
          setStatus('Restart failed.');
        } finally {
          btnRestart.disabled = false;
        }
      };

      btnLogin.onclick = async () => {
        loginError.style.display = 'none';
        setStatus('Signing in…');

        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;

        const res = await fetch('/api/v1/auths/signin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password })
        });

        if (!res.ok) {
          const text = await res.text();
          showLogin('Sign in failed. ' + text);
          setStatus('Sign in failed.');
          return;
        }

        try {
          const data = await res.json();
          if (data && data.token) authToken = data.token;
        } catch {
          // ignore
        }

        const ok = await checkAdmin();
        if (!ok) {
          showLogin('Signed in, but this account is not admin.');
          setStatus('Not an admin account.');
          return;
        }

        startStream();
      };

      btnRetry.onclick = () => {
        loginError.style.display = 'none';
        startStream();
      };

      // Start immediately.
      startStream();
    })();
    """


@router.get("/admin/console", response_class=HTMLResponse)
async def admin_console_page() -> HTMLResponse:
  return HTMLResponse(
    _CONSOLE_HTML,
    headers={
      "Cache-Control": "no-store, max-age=0",
      "Pragma": "no-cache",
    },
  )


@router.get("/admin/console/app.js")
async def admin_console_js() -> PlainTextResponse:
  return PlainTextResponse(
    _CONSOLE_JS,
    media_type="application/javascript",
    headers={
      "Cache-Control": "no-store, max-age=0",
      "Pragma": "no-cache",
    },
  )


@router.get("/admin/console/")
async def admin_console_page_slash() -> RedirectResponse:
    return RedirectResponse(url="/admin/console")


@router.get("/admin/console/stream")
async def admin_console_stream(request: Request, _user=Depends(get_admin_user)):
    """Server-Sent Events stream of recent + live log lines (admin only)."""

    stream = get_console_stream()

    async def event_gen():
        # Send last buffer first.
        for line in stream.get_buffer_snapshot():
            yield f"data: {json.dumps({'line': line})}\n\n"

        queue = await stream.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    line = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps({'line': line})}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive comment to keep proxies from buffering/closing.
                    yield ": keepalive\n\n"
        finally:
            await stream.unsubscribe(queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/admin/console/stream/")
async def admin_console_stream_slash() -> RedirectResponse:
    return RedirectResponse(url="/admin/console/stream")


@router.post("/admin/console/restart-owui")
async def admin_console_restart_owui(_user=Depends(get_admin_user)):
  stream = get_console_stream()
  await stream.publish("[system] Restart requested by admin; shutting down OWUI process...")

  def _terminate() -> None:
    os._exit(0)

  threading.Timer(0.35, _terminate).start()
  return {"ok": True, "message": "OWUI restart signal sent."}
