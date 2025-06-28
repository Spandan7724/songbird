from __future__ import annotations
import asyncio, os, textwrap, httpx, requests, litellm
from typing import List, Tuple

# ────────────────────────────────────────────────────────────────────────────
# CONFIG
API_KEY          = os.getenv("GEMINI_API_KEY")
BASE_URL         = "https://generativelanguage.googleapis.com/v1beta/models"
PER_MODEL_TIMEOUT = 10          # seconds
MAX_CONCURRENCY   = 6           # parallel LiteLLM probes

if not API_KEY:
    raise SystemExit("❌  GEMINI_API_KEY not set.  Run:  export GEMINI_API_KEY=<key>")

# ────────────────────────────────────────────────────────────────────────────
# PHASE A – fetch catalogue  (with pagination support)
def list_ai_studio_models() -> List[str]:
    params: dict[str, str | None] = {"key": API_KEY}
    acc: List[str] = []
    while True:
        rsp = requests.get(BASE_URL, params=params, timeout=15)
        rsp.raise_for_status()
        payload = rsp.json()
        acc.extend(
            m["name"].split("/", 1)[1]             # keep "gemini-1.5-flash"
            for m in payload.get("models", [])
            if m["name"].startswith("models/gemini")
        )
        if "nextPageToken" not in payload:
            break
        params["pageToken"] = payload["nextPageToken"]
    return sorted(set(acc))

# ────────────────────────────────────────────────────────────────────────────
# PHASE B – probe each model with LiteLLM
async def probe(model: str) -> Tuple[str, bool, str | None]:
    try:
        await litellm.acompletion(
            model=f"gemini/{model}",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            timeout=PER_MODEL_TIMEOUT,
        )
        return model, True, None
    except Exception as exc:
        return model, False, str(exc).splitlines()[0]

async def run_probes(models: List[str]) -> None:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def bound_probe(m):
        async with sem:
            return await probe(m)

    tasks = [asyncio.create_task(bound_probe(m)) for m in models]
    ok, bad = [], []
    for t in asyncio.as_completed(tasks):
        name, success, err = await t
        if success:
            ok.append(name)
            print(f"✓ {name}")
        else:
            bad.append((name, err))
            print(f"✗ {name:30} — {err}")

    # summary
    print("\n────────── SUMMARY ──────────")
    print("Working:", ", ".join(ok) if ok else "(none)")
    if bad:
        print("Failed :", ", ".join(n for n, _ in bad))

# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching Gemini catalogue from Google AI Studio …")
    model_names = list_ai_studio_models()
    print(f"Discovered {len(model_names)} model(s). Probing via LiteLLM …\n")
    asyncio.run(run_probes(model_names))