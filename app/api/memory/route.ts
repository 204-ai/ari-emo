import { NextResponse } from "next/server";

export const runtime = "nodejs";

const MEMORY_SERVER = process.env.MEMORY_SERVER_URL || "http://127.0.0.1:8192";

/**
 * Proxy to the SQLite memory server.
 *
 * GET /api/memory?action=stats
 * GET /api/memory?action=sessions&limit=20
 * GET /api/memory?action=messages&session_id=xxx
 * GET /api/memory?action=search&q=keyword
 * GET /api/memory?action=recent&limit=50
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const action = url.searchParams.get("action") || "stats";

  try {
    let target: string;

    switch (action) {
      case "stats":
        target = `${MEMORY_SERVER}/stats`;
        break;
      case "sessions":
        target = `${MEMORY_SERVER}/sessions?limit=${url.searchParams.get("limit") || 20}&offset=${url.searchParams.get("offset") || 0}`;
        break;
      case "messages": {
        const sid = url.searchParams.get("session_id");
        if (!sid) return NextResponse.json({ error: "session_id required" }, { status: 400 });
        target = `${MEMORY_SERVER}/sessions/${sid}/messages?limit=${url.searchParams.get("limit") || 200}`;
        break;
      }
      case "search":
        target = `${MEMORY_SERVER}/search?q=${encodeURIComponent(url.searchParams.get("q") || "")}&limit=${url.searchParams.get("limit") || 20}`;
        break;
      case "recent":
        target = `${MEMORY_SERVER}/recent?limit=${url.searchParams.get("limit") || 50}`;
        break;
      default:
        return NextResponse.json({ error: "unknown action" }, { status: 400 });
    }

    const res = await fetch(target);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    console.error("[memory-api] Error:", err);
    return NextResponse.json(
      { error: "Memory server unavailable", details: String(err) },
      { status: 502 }
    );
  }
}

/**
 * POST /api/memory
 *
 * Body: { action: "message", session_id, role, content, token_estimate? }
 *       { action: "session", session_id? }
 *       { action: "end_session", session_id, summary? }
 *       { action: "search", query, role_filter?, limit? }
 */
export async function POST(req: Request) {
  const body = await req.json();
  const action = body.action || "message";

  try {
    let target: string;
    let payload: Record<string, unknown>;

    switch (action) {
      case "session":
        target = `${MEMORY_SERVER}/sessions`;
        payload = { session_id: body.session_id };
        break;
      case "end_session":
        target = `${MEMORY_SERVER}/sessions/${body.session_id}/end`;
        payload = { summary: body.summary };
        break;
      case "message":
        target = `${MEMORY_SERVER}/messages`;
        payload = {
          session_id: body.session_id,
          role: body.role,
          content: body.content,
          token_estimate: body.token_estimate,
        };
        break;
      case "search":
        target = `${MEMORY_SERVER}/search`;
        payload = {
          query: body.query,
          role_filter: body.role_filter,
          limit: body.limit || 20,
        };
        break;
      default:
        return NextResponse.json({ error: "unknown action" }, { status: 400 });
    }

    const res = await fetch(target, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[memory-api] Error:", err);
    return NextResponse.json(
      { error: "Memory server unavailable", details: String(err) },
      { status: 502 }
    );
  }
}
