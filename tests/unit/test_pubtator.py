"""PubTator's export, as it actually answers.

Written around the failure the first full harvest had: PubTator answers a PMID
it does not hold with nothing, and a batch of nothing but such PMIDs with HTTP
400. Both were asked about again on every run, and the 400 stopped the run.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from vitiligo.sources.pubtator import PubtatorClient

HELD = {"111"}


def test_a_pmid_pubtator_does_not_hold_is_asked_about_once(tmp_path: Path) -> None:
    asked: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pmids = request.url.params["pmids"].split(",")
        asked.append(pmids)
        found = [{"pmid": p, "passages": [], "relations": []} for p in pmids if p in HELD]
        if not found:
            return httpx.Response(400, json={"detail": "Could not retrieve publications"})
        return httpx.Response(200, json={"PubTator3": found})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = PubtatorClient(client=http, delay=0, cache=tmp_path)
        assert [n for _, n in client.harvest(["111", "999"])] == [1]
        assert [n for _, n in client.harvest(["111", "999", "888"])] == [0]
        assert [n for _, n in client.harvest(["111", "999", "888"])] == []

    assert asked == [["111", "999"], ["888"]]
