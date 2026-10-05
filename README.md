# Loom — a brainstorming partner that asks, not tells

Loom is a Socratic agent for developing a raw idea. It never recommends. In the background it runs live
[SerpApi](https://serpapi.com) searches (Google Scholar / Google News / Google), distills them into private notes,
and uses those notes to ask sharper questions. Everything it learns becomes a graph you can explore, and you can
ask "What have you found?" at any time. When you end the session you get a map of the idea and its open questions.

## How it works
1. **Knowledge layer** (`agent.py::_background`) — after each user message an LLM extracts new concepts. If one is new, it
   fires **one** search; bucket picks the engine: research → Scholar, market → News, else → Google (`search.py`).
   Results are distilled into notes `{claim, tension_or_gap, source_url}` (source URL is validated against the results).
2. **Socratic layer** (`agent.py::chat`) — gets a digest of the latest notes and asks one question. No search results? It asks
   a plain question; failures are silent.
3. **Resurfacing** — graph of `idea_concept` and `resource_note` nodes (edge = "relates to"), the on-demand findings button,
   and a closing landscape of themes + open questions + sources.

Single session, in memory, no login.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add SERPAPI_API_KEY and your Gemini API key as LOOM_MODEL
uvicorn main:app --reload
# open http://localhost:8000
```

## Demo script
Idea: *an AI study buddy for university students that answers questions from their own lecture notes (RAG).*
Try mentioning: retrieval hallucination (→ Scholar), existing study-app competitors (→ News), then ask
"What have you found?", click graph nodes, and end the session.
