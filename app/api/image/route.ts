import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { join } from "path";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const file = searchParams.get("file");
  const source = searchParams.get("source") || "generated";

  if (!file || /[/\\]/.test(file)) {
    return NextResponse.json({ error: "Invalid filename" }, { status: 400 });
  }

  const validSources = ["generated", "uploads"];
  if (!validSources.includes(source)) {
    return NextResponse.json({ error: "Invalid source" }, { status: 400 });
  }

  const filePath = join(process.cwd(), source, file);

  try {
    const data = await readFile(filePath);
    const ext = file.split(".").pop()?.toLowerCase();
    const mime =
      ext === "png"
        ? "image/png"
        : ext === "jpg" || ext === "jpeg"
          ? "image/jpeg"
          : ext === "webp"
            ? "image/webp"
            : "application/octet-stream";

    return new Response(data, {
      headers: {
        "Content-Type": mime,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
}
