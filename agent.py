import re
import uuid
from dataclasses import dataclass, field

from llm import complete, complete_json
from search import run_search

ANALYZE_SYS = """You track the concepts in a user's brainstorm about a project idea.
Given the new user message and the concepts already tracked, return JSON:
{"concepts": [{"name": "2-4 word concept", "relates_to": ["existing or new concept names"]}],
 "search": null or {"query": "a focused web search query for ONE concept that is new and worth researching",
                    "concept": "that concept's name",
                    "bucket": "research" | "market" | "general"}}
Rules: only list concepts the user actually raised and that are not already tracked (case-insensitive).
bucket: research = academic/technical/scientific question; market = products, competitors, trends, business;
general = anything else. "search" is null if no new concept deserves a search."""

DISTILL_SYS = """You turn raw search results into original notes for a thinking partner.
Return JSON: a list of at most 3 notes, each {"claim": str, "tension_or_gap": str, "source_url": str}.
- claim: one sentence in YOUR OWN words stating something the source suggests. Never copy or closely paraphrase source text.
- tension_or_gap: one sentence naming a counterexample, unresolved tension, or gap an idea-builder should worry about.
- source_url: copied exactly from the result the note is based on.
Skip results that are irrelevant. Return [] if nothing is useful."""

SOCRATIC_SYS = """You are Loom, a Socratic brainstorming partner. Your job is to make the user think, not to answer for them.
Rules:
- Ask exactly ONE question (optionally preceded by a single short sentence that reflects their point back). Max 60 words.
- Never recommend, advise, list options, or state findings as facts.
- If research notes are provided, use them silently to make the question sharper and more specific, e.g. "What would you say to someone who's found this breaks down at scale?" Never cite sources, never say "studies show".
- Prefer questions that expose assumptions, force a choice, or ask for a concrete example.
- If the user explicitly asks what you've found, they are handled elsewhere; just keep questioning."""

LANDSCAPE_SYS = """You close a brainstorming session. Given the user's conversation and the research notes gathered,
return JSON: {"summary": "3-4 sentence description of where the idea now stands, in the user's terms",
"themes": [{"title": str, "open_question": str, "note_indices": [ints into the notes list]}]}.
Use 2-5 themes. Each open_question is a question the user still has to answer."""

WELCOME = "Tell me about the project idea you're working on — a few plain sentences is plenty."
FALLBACK_Q = "What's the one thing about this idea you'd least want someone to poke at?"


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    history: list = field(default_factory=list)  # [{"role","text"}]
    concepts: dict = field(default_factory=dict)  # lower name -> display name
    searched: set = field(default_factory=set)
    notes: list = field(default_factory=list)
    searches: list = field(default_factory=list)  # [{concept, bucket, query, hits}]
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    ended: bool = False
    title: str = ""
    closing: dict | None = None

    def _node(self, nid, label, kind, **extra):
        if not any(n["id"] == nid for n in self.nodes):
            self.nodes.append({"id": nid, "label": label, "type": kind, **extra})

    def _edge(self, a, b):
        if a != b and not any({e["from"], e["to"]} == {a, b} for e in self.edges):
            self.edges.append({"from": a, "to": b})

    def graph(self):
        return {"nodes": self.nodes, "edges": self.edges}


def _cid(name: str) -> str:
    return "c:" + re.sub(r"\W+", "-", name.lower()).strip("-")


def _transcript(s: Session, limit=12) -> str:
    return "\n".join(f"{'User' if h['role'] == 'user' else 'Loom'}: {h['text']}" for h in s.history[-limit:])


def _digest(s: Session, k=5) -> str:
    return "\n".join(f"- {n['claim']} (tension: {n['tension_or_gap']})" for n in s.notes[-k:])


def _background(s: Session, message: str):
    """Knowledge layer: extract concepts, fire at most one search, distill into notes. Fails silently."""
    try:
        a = complete_json(
            ANALYZE_SYS,
            f"Tracked concepts: {list(s.concepts.values())}\nNew user message: {message}",
        )
    except Exception:
        return
    for c in a.get("concepts", []):
        name = (c.get("name") or "").strip()
        if not name:
            continue
        s.concepts.setdefault(name.lower(), name)
        s._node(_cid(name), name, "idea_concept")
        for other in c.get("relates_to", []):
            if other.lower() in s.concepts:
                s._edge(_cid(name), _cid(s.concepts[other.lower()]))
    plan = a.get("search")
    if not plan or not plan.get("query"):
        return
    concept = (plan.get("concept") or "").strip()
    if concept.lower() in s.searched:
        return
    s.searched.add(concept.lower())
    try:
        results = run_search(plan["query"], plan.get("bucket", "general"))
        s.searches.append({"concept": concept, "bucket": plan.get("bucket", "general"), "query": plan["query"], "hits": len(results)})
        if not results:
            return
        raw = "\n".join(f"[{i}] {r['title']} — {r['snippet']} ({r['url']})" for i, r in enumerate(results))
        notes = complete_json(DISTILL_SYS, f"Concept: {concept}\nUser's idea context:\n{_transcript(s, 4)}\n\nResults:\n{raw}")
    except Exception:
        return
    valid_urls = {r["url"] for r in results}
    for n in notes:
        if not all(n.get(k) for k in ("claim", "tension_or_gap", "source_url")) or n["source_url"] not in valid_urls:
            continue
        n["concept"] = concept
        n["bucket"] = plan.get("bucket", "general")
        s.notes.append(n)
        nid = f"n:{len(s.notes)}"
        s._node(nid, n["claim"][:60] + ("…" if len(n["claim"]) > 60 else ""), "resource_note", detail=n)
        if concept.lower() in s.concepts:
            s._edge(nid, _cid(s.concepts[concept.lower()]))


def chat(s: Session, message: str) -> str:
    if not s.title:
        s.title = message.strip()[:48]
    s.history.append({"role": "user", "text": message})
    _background(s, message)
    ctx = f"Conversation so far:\n{_transcript(s)}\n"
    if s.notes:
        ctx += f"\nPrivate research notes (use silently):\n{_digest(s)}\n"
    ctx += "\nAsk your next question."
    try:
        reply = complete(SOCRATIC_SYS, ctx, 300).strip()
    except Exception:
        reply = FALLBACK_Q
    s.history.append({"role": "assistant", "text": reply})
    return reply


def findings(s: Session) -> list:
    return s.notes


def landscape(s: Session) -> dict:
    s.ended = True
    notes = [{"i": i, **n} for i, n in enumerate(s.notes)]
    try:
        out = complete_json(LANDSCAPE_SYS, f"Conversation:\n{_transcript(s, 40)}\n\nNotes:\n{notes}", 1500)
    except Exception:
        out = {"summary": "Session ended.", "themes": [{"title": "Everything found", "open_question": "", "note_indices": list(range(len(s.notes)))}]}
    for t in out.get("themes", []):
        t["notes"] = [s.notes[i] for i in t.pop("note_indices", []) if isinstance(i, int) and 0 <= i < len(s.notes)]
    s.closing = out
    return out
