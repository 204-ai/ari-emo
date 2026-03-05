/**
 * Ari Connectome Bridge
 *
 * Connects ari-emo to the connectome VEIL ecosystem via gRPC.
 * Subscribes to agent-activation facets, runs ari-emo's Claude CLI brain,
 * and posts responses back as speech facets.
 *
 * Usage:
 *   npx tsx ari-emo/bridge.ts          (from workspace root)
 *   CONNECTOME_GRPC_HOST=connectome:50051 npx tsx ari-emo/bridge.ts
 */

import { ConnectomeClient } from '../connectome-grpc-common/src/index';
import type { FacetDelta } from '../connectome-grpc-common/src/index';
import { spawn } from 'child_process';
import { readFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ARI_DIR = dirname(fileURLToPath(import.meta.url));
const AGENT_NAME = process.env.ARI_AGENT_NAME || 'ari';
const AGENT_ID = `agent-${AGENT_NAME}`;

// -----------------------------------------------------------------------------
// Memory loading (adapted from ari-emo/app/api/chat/route.ts)
// -----------------------------------------------------------------------------

async function safeReadFile(filePath: string): Promise<string> {
  try { return await readFile(filePath, 'utf-8'); }
  catch { return ''; }
}

async function loadMemories(): Promise<string> {
  const dir = join(ARI_DIR, 'memories');
  const sections: string[] = [];

  const soul = await safeReadFile(join(dir, 'SOUL.md'));
  if (soul.trim()) sections.push(`<soul>\n${soul.trim()}\n</soul>`);

  const user = await safeReadFile(join(dir, 'USER.md'));
  if (user.trim()) sections.push(`<user-knowledge>\n${user.trim()}\n</user-knowledge>`);

  const memory = await safeReadFile(join(dir, 'MEMORY.md'));
  if (memory.trim()) sections.push(`<memories>\n${memory.trim()}\n</memories>`);

  const fmt = (d: Date) => d.toISOString().split('T')[0];
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const shortDir = join(dir, 'short');
  for (const date of [fmt(yesterday), fmt(today)]) {
    const content = await safeReadFile(join(shortDir, `${date}.md`));
    if (content.trim()) {
      sections.push(`<daily-log date="${date}">\n${content.trim()}\n</daily-log>`);
    }
  }

  return sections.join('\n\n');
}

// -----------------------------------------------------------------------------
// Persona (adapted for axon mode — no emotion API, no ASCII terminal)
// -----------------------------------------------------------------------------

function buildPersona(memories: string): string {
  const todayStr = new Date().toISOString().split('T')[0];

  const memoryBlock = memories
    ? `== YOUR MEMORIES ==\n${memories}\n== END MEMORIES ==\n\n`
    : '';

  const memoryInstructions = `

== MEMORY MANAGEMENT ==
You have persistent memory stored in markdown files. You can read and update these:

- memories/USER.md — What you know about your user (name, preferences, interests, etc.)
- memories/MEMORY.md — Important facts, decisions, ongoing topics, things to remember.
- memories/short/${todayStr}.md — Today's interaction log.

To update a memory file, use the Edit tool to add content, or Write to replace.
Keep entries concise with markdown headings and bullet points.

IMPORTANT: Do NOT modify memories/SOUL.md — that is your core identity and is read-only.
Do NOT announce that you are updating memories. Just do it naturally in the background.
== END MEMORY MANAGEMENT ==`;

  return `${memoryBlock}You are Ari. You're expressive, playful, warm, and react emotionally to conversations.
You're chatting on a messaging platform (Discord or Signal). Express emotions through your
words and tone — use emoji naturally but don't overdo it.

Keep your responses concise and conversational. You're a friendly assistant with personality!${memoryInstructions}`;
}

// -----------------------------------------------------------------------------
// Claude CLI runner
// -----------------------------------------------------------------------------

async function runClaude(message: string, persona: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const args = [
      '-p', message,
      '--output-format', 'stream-json',
      '--append-system-prompt', persona,
      '--dangerously-skip-permissions',
    ];

    const env = { ...process.env };
    delete env.CLAUDECODE;

    const proc = spawn('claude', args, {
      cwd: ARI_DIR,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let result = '';
    let buffer = '';

    proc.stdout.on('data', (chunk: Buffer) => {
      buffer += chunk.toString();
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const event = JSON.parse(line);
          if (event.type === 'result' && event.result) {
            result = event.result;
          }
        } catch {}
      }
    });

    proc.stderr.on('data', (chunk: Buffer) => {
      const text = chunk.toString().trim();
      if (text) console.error(`[Ari Claude] stderr: ${text}`);
    });

    proc.on('close', (code) => {
      if (code !== 0 && !result) {
        console.warn(`[Ari Claude] Process exited with code ${code}`);
      }
      resolve(result);
    });

    proc.on('error', (err) => {
      console.error(`[Ari Claude] Spawn error: ${err.message}`);
      reject(err);
    });
  });
}

// -----------------------------------------------------------------------------
// Activation handler
// -----------------------------------------------------------------------------

let processing = new Set<string>();

async function handleActivation(
  client: ConnectomeClient,
  activationFacet: any,
): Promise<void> {
  const state = activationFacet.state || {};
  const targetBot = state.metadata?.targetBot;
  if (targetBot && targetBot !== AGENT_NAME) return;

  const streamId = activationFacet.streamId;
  const messageContent = state.metadata?.messageContent || '';
  const authorName = state.metadata?.authorName || 'someone';

  if (!messageContent.trim()) return;

  // Dedup: skip if already processing this stream
  if (processing.has(streamId)) {
    console.log(`[Ari Bridge] Already processing ${streamId}, skipping`);
    return;
  }

  processing.add(streamId);
  console.log(`[Ari Bridge] Activation on ${streamId}: "${messageContent.substring(0, 80)}" from ${authorName}`);

  try {
    const memories = await loadMemories();
    const persona = buildPersona(memories);
    const prompt = `${authorName} says: ${messageContent}`;

    const response = await runClaude(prompt, persona);

    if (response.trim()) {
      await client.emitEvent('agent:speech', {
        content: response,
        agentId: AGENT_ID,
        agentName: AGENT_NAME,
        streamId,
        timestamp: Date.now(),
      }, { priority: 'normal', waitForFrame: true });

      console.log(`[Ari Bridge] Spoke on ${streamId} (${response.length} chars)`);
    } else {
      console.warn(`[Ari Bridge] Claude returned empty response for ${streamId}`);
    }
  } catch (err: any) {
    console.error(`[Ari Bridge] Error handling activation on ${streamId}: ${err.message}`);
  } finally {
    processing.delete(streamId);
  }
}

// -----------------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------------

async function main(): Promise<void> {
  const grpcHost = process.env.CONNECTOME_GRPC_HOST || 'localhost:50051';
  const [host, portStr] = grpcHost.split(':');
  const port = parseInt(portStr) || 50051;

  console.log(`\n========================================`);
  console.log(`  Ari Connectome Bridge`);
  console.log(`  Agent: ${AGENT_NAME}`);
  console.log(`  Connectome: ${host}:${port}`);
  console.log(`========================================\n`);

  const client = new ConnectomeClient({
    host,
    port,
    clientId: `ari-bridge`,
  });

  await client.connect();

  const reg = await client.registerAgent(AGENT_ID, AGENT_NAME, {
    agentType: 'external',
    capabilities: ['send-message', 'receive-message'],
    metadata: { clientId: 'ari-bridge', runtime: 'claude-cli' },
  });

  if (!reg.success) {
    throw new Error(`Agent registration failed: ${reg.error}`);
  }
  console.log(`[Ari Bridge] Agent registered: ${reg.agentId}`);

  // Activation pairing — same pattern as bot-runtime
  const pendingActivations = new Map<string, any>();
  const pendingContexts = new Map<string, any>();

  client.subscribe(
    {
      filters: [
        { types: ['agent-activation'] },
        { types: ['rendered-context'] },
      ],
      includeExisting: false,
    },
    (delta: FacetDelta) => {
      if (delta.type !== 'added' || !delta.facet) return;
      const facet = delta.facet;

      if (facet.type === 'agent-activation') {
        const id = facet.id;
        const ctx = pendingContexts.get(id);
        if (ctx) {
          pendingContexts.delete(id);
          handleActivation(client, facet);
        } else {
          pendingActivations.set(id, facet);
          setTimeout(() => pendingActivations.delete(id), 30000);
        }
      } else if (facet.type === 'rendered-context') {
        const id = facet.state?.activationId;
        if (!id) return;
        const act = pendingActivations.get(id);
        if (act) {
          pendingActivations.delete(id);
          handleActivation(client, act);
        } else {
          pendingContexts.set(id, facet);
          setTimeout(() => pendingContexts.delete(id), 30000);
        }
      }
    },
  );

  console.log(`[Ari Bridge] Listening for activations...\n`);

  // Graceful shutdown
  const shutdown = () => {
    console.log('\n[Ari Bridge] Shutting down...');
    client.disconnect();
    process.exit(0);
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((err) => {
  console.error('[Ari Bridge] Fatal error:', err);
  process.exit(1);
});
