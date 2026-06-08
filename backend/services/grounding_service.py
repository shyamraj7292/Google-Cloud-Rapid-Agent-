"""
Copa Agent — Grounding Service (Vertex AI Search + local fallback)
==================================================================

Copa Agent doesn't fix things from vibes — it grounds its decisions in the
team's own runbooks and playbooks, then *cites* the section it followed. That
turns "the AI guessed" into "the AI followed Pipeline Playbook §1: Unit Test
Failures", which is exactly the kind of traceable, auditable behavior judges and
real ops teams want.

Two modes, same return shape:

  • VERTEX — when VERTEX_SEARCH_DATASTORE_ID (a Vertex AI Search / Discovery
             Engine data store) is configured, queries it for grounded snippets.

  • LOCAL  — otherwise, indexes the markdown runbooks/playbooks under
             agent/datastores/ in-process and does lightweight keyword-overlap
             retrieval. Good enough to demo real citations with zero cloud setup.

Returns: {"ok": bool, "citations": [{"source", "section", "snippet"}], "mode"}.
"""

import os
import re
import glob
import logging
from typing import Optional

logger = logging.getLogger("copa-agent.services.grounding")

try:
    from google.cloud import discoveryengine_v1 as discoveryengine
    from google.api_core.client_options import ClientOptions
    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False

_STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "of", "in", "on", "for", "and", "or",
    "with", "at", "by", "it", "this", "that", "be", "as", "from", "was", "has",
    "i", "you", "we", "my", "your", "can", "if", "not", "but", "so",
}


def _tokenize(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 2 and w not in _STOPWORDS}


class GroundingService:
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.search_location = os.getenv("VERTEX_SEARCH_LOCATION", "global")
        self.datastore_id = os.getenv("VERTEX_SEARCH_DATASTORE_ID", "")
        self.client = None
        self.mode = "local"

        if DISCOVERY_AVAILABLE and self.project_id and self.datastore_id:
            try:
                opts = ClientOptions(
                    api_endpoint=f"{self.search_location}-discoveryengine.googleapis.com"
                    if self.search_location != "global" else None
                )
                self.client = discoveryengine.SearchServiceClient(client_options=opts)
                self.mode = "vertex"
                logger.info(f"Grounding: VERTEX AI Search (datastore {self.datastore_id}).")
            except Exception as e:
                logger.warning(f"Vertex Search init failed: {e}; using local grounding.")

        # Build the local section index regardless (used as fallback).
        self._sections = self._index_local_datastores()
        if self.mode == "local":
            logger.info(f"Grounding: LOCAL ({len(self._sections)} runbook sections indexed).")

    # -- local index ---------------------------------------------------------
    def _index_local_datastores(self) -> list:
        base = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "datastores")
        sections = []
        for path in glob.glob(os.path.join(base, "*.md")):
            source = os.path.splitext(os.path.basename(path))[0]
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                continue
            # Split on ## / ### headings, keep the heading as the section title.
            parts = re.split(r"(?m)^(#{2,3})\s+(.+)$", text)
            # parts = [pre, '##', 'Title', body, '###', 'Title2', body2, ...]
            i = 1
            while i + 2 < len(parts):
                title = parts[i + 1].strip()
                body = parts[i + 2].strip()
                if body:
                    sections.append({
                        "source": source,
                        "section": title,
                        "snippet": body[:500],
                        "_tokens": _tokenize(title + " " + body),
                    })
                i += 3
        return sections

    # -- public --------------------------------------------------------------
    def search(self, query: str, top_k: int = 2) -> dict:
        if self.mode == "vertex":
            try:
                return self._search_vertex(query, top_k)
            except Exception as e:
                logger.warning(f"Vertex search failed at query time: {e}; using local.")
        return self._search_local(query, top_k)

    def _search_local(self, query: str, top_k: int) -> dict:
        q = _tokenize(query)
        scored = []
        for s in self._sections:
            overlap = len(q & s["_tokens"])
            if overlap:
                scored.append((overlap, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        citations = [{
            "source": s["source"], "section": s["section"], "snippet": s["snippet"],
        } for _, s in scored[:top_k]]
        return {"ok": True, "mode": "local", "citations": citations}

    def _search_vertex(self, query: str, top_k: int) -> dict:
        serving_config = (
            f"projects/{self.project_id}/locations/{self.search_location}"
            f"/collections/default_collection/dataStores/{self.datastore_id}"
            f"/servingConfigs/default_config"
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config, query=query, page_size=top_k,
        )
        response = self.client.search(request)
        citations = []
        for result in response.results:
            doc = result.document
            data = dict(doc.derived_struct_data) if getattr(doc, "derived_struct_data", None) else {}
            snippet = ""
            if "snippets" in data and data["snippets"]:
                snippet = data["snippets"][0].get("snippet", "")
            citations.append({
                "source": data.get("title", doc.name.split("/")[-1]),
                "section": data.get("link", ""),
                "snippet": snippet[:500],
            })
        return {"ok": True, "mode": "vertex", "citations": citations}
