"""
Add new emotions to Ari the hamster!
Run: python add_emotions.py

Each emotion needs:
  - A name
  - Eyes (3 chars like "^.^")
  - Mouth (1 char)
  - Cheeks (2-char left, 2-char right) — use "  " for none
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent

# ── Define new emotions here ─────────────────────────────────────────
NEW_EMOTIONS = {
    "confused":    {"eyes": "?.?", "mouth": "S", "cheeks": ("  ", "  ")},
    "hungry":      {"eyes": "9.9", "mouth": "Q", "cheeks": ("~ ", " ~")},
    "mischievous": {"eyes": "¬.¬", "mouth": ">", "cheeks": ["  ", "  "]},
}
# ─────────────────────────────────────────────────────────────────────

API_ROUTE = ROOT / "app" / "api" / "emotion" / "route.ts"
HAMSTER_PANE = ROOT / "app" / "components" / "HamsterPane.tsx"


def patch_emotion_list(text: str, names: list[str]) -> str:
    """Insert new emotion strings into a TS array like VALID_EMOTIONS / EMOTIONS."""
    # Match the last entry before '] as const'
    pattern = r'("neutral",?\s*\n)(\] as const;)'
    new_entries = "".join(f'  "{name}",\n' for name in names)
    return re.sub(pattern, rf"\1{new_entries}\2", text)


def patch_emotion_map(text: str, emotions: dict) -> str:
    """Insert new entries into the EMOTION_MAP object."""
    # Find the closing of the neutral entry to insert after it
    lines = text.split("\n")
    insert_idx = None
    for i, line in enumerate(lines):
        if "neutral:" in line and "eyes:" in line:
            insert_idx = i + 1
            break

    if insert_idx is None:
        raise ValueError("Could not find 'neutral' entry in EMOTION_MAP")

    new_lines = []
    for name, parts in emotions.items():
        eyes = parts["eyes"]
        mouth = parts["mouth"]
        lc, rc = parts["cheeks"]
        padding = " " * max(1, 11 - len(name))
        new_lines.append(
            f'  {name}:{padding}{{ eyes: "{eyes}", mouth: "{mouth}",'
            f'   cheeks: ["{lc}", "{rc}"] }},'
        )

    lines = lines[:insert_idx] + new_lines + lines[insert_idx:]
    return "\n".join(lines)


def main():
    names = list(NEW_EMOTIONS.keys())

    # ── Patch API route ──
    api_text = API_ROUTE.read_text(encoding="utf-8")
    api_text = patch_emotion_list(api_text, names)
    API_ROUTE.write_text(api_text, encoding="utf-8")
    print(f"[ok] Patched {API_ROUTE.relative_to(ROOT)}")

    # ── Patch HamsterPane ──
    pane_text = HAMSTER_PANE.read_text(encoding="utf-8")
    pane_text = patch_emotion_list(pane_text, names)
    pane_text = patch_emotion_map(pane_text, NEW_EMOTIONS)
    HAMSTER_PANE.write_text(pane_text, encoding="utf-8")
    print(f"[ok] Patched {HAMSTER_PANE.relative_to(ROOT)}")

    print(f"\nAdded {len(names)} new emotions: {', '.join(names)}")
    print("Restart your Next.js dev server to see them!")


if __name__ == "__main__":
    main()
