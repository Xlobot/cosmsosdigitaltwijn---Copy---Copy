/**
 * COSMOS Telemetry Client Examples (JavaScript / TypeScript / React / Node.js)
 * ===========================================================================
 * Demonstrates 3 flexible ways to stream live satellite telemetry:
 * 1. REST Polling (Universal, works in any environment)
 * 2. WebSocket (Zero-latency push stream, ideal for 60 FPS 3D Three.js globes)
 * 3. Server-Sent Events (SSE / EventSource, native browser streaming)
 */

// ==========================================
// 1. REST Incremental Poller (Universal)
// ==========================================
export function startTelemetryPolling(generatorUrl = 'http://localhost:8080', onFrame) {
  let cursor = 0;
  let isRunning = true;

  async function poll() {
    if (!isRunning) return;
    try {
      const response = await fetch(`${generatorUrl}/rows?since=${cursor}&limit=50`);
      if (response.ok) {
        const rows = await response.json();
        for (const row of rows) {
          cursor++;
          if (onFrame) onFrame(row);
        }
      }
    } catch (err) {
      console.warn('[TelemetryClient] Polling error:', err.message);
    }
    setTimeout(poll, 400); // 400ms poll interval
  }

  poll();

  return () => {
    isRunning = false; // Call to disconnect
  };
}

// ==========================================
// 2. Real-Time WebSocket Stream (Recommended for 3D UI)
// ==========================================
export function startWebSocketStream(wsUrl = 'ws://localhost:8080/ws', onFrame) {
  let ws = new WebSocket(wsUrl);
  let shouldReconnect = true;

  ws.onmessage = (event) => {
    try {
      const frame = JSON.parse(event.data);
      if (onFrame) onFrame(frame);
    } catch (err) {
      console.error('[WebSocket] Parse error:', err);
    }
  };

  ws.onerror = (err) => console.warn('[WebSocket] Error:', err);

  ws.onclose = () => {
    if (shouldReconnect) {
      console.log('[WebSocket] Connection closed. Reconnecting in 1s...');
      setTimeout(() => {
        if (shouldReconnect) startWebSocketStream(wsUrl, onFrame);
      }, 1000);
    }
  };

  return () => {
    shouldReconnect = false;
    ws.close();
  };
}

// ==========================================
// 3. Server-Sent Events (SSE / EventSource)
// ==========================================
export function startEventSourceStream(sseUrl = 'http://localhost:8080/stream', onFrame) {
  const eventSource = new EventSource(sseUrl);

  eventSource.onmessage = (event) => {
    try {
      const frame = JSON.parse(event.data);
      if (onFrame) onFrame(frame);
    } catch (err) {
      console.error('[SSE] Parse error:', err);
    }
  };

  eventSource.onerror = (err) => {
    console.warn('[SSE] Connection error. Browser will auto-reconnect.');
  };

  return () => {
    eventSource.close();
  };
}

// ==========================================
// 4. Quick CLI Test for Node.js
// ==========================================
if (typeof window === 'undefined' && typeof process !== 'undefined') {
  console.log('Testing Node.js REST poller against http://127.0.0.1:8080...');
  startTelemetryPolling('http://127.0.0.1:8080', (row) => {
    console.log(`[Frame #${row.emit_index}] ${row.timestamp} | Pos: (${row.position_x}, ${row.position_y}, ${row.position_z}) km | Batt: ${row.battery_percentage}% | Temp: ${row.temperature}°C`);
  });
}
