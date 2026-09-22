#!/usr/bin/env python3
"""Generate The Tech Briefing static information network from data/network.json."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.lib import assets
from scripts.lib.components import bar_rows, chips, empty, numbered, row, source_rows
from scripts.lib.html_utils import e, index_by, load, page_file, pretty_date, short_date, write
from scripts.lib.layout import breadcrumbs, crumb_ld, layout
from scripts.lib.ingest.sources import load_sources
from scripts.lib.country_intel import country_records, world_country_registry
from scripts.lib.ingest.sectors import SECTOR_LABELS
from scripts.lib.ingest.classify import primary_sector_label
from scripts.lib.intelligence.access import IntelligenceStore
from scripts.lib.intelligence.build import write_intelligence_public
from scripts.lib.intelligence.country_events import country_event_summary
from scripts.lib.paths import ROOT, RSS_INBOX_PATH, VOXEL_COUNTRIES_PATH, XENO_MAIN
from scripts.lib.stable_json import write_if_changed

TOPIC_SHORT = {
    "ai": "AI",
    "robotics": "ROBOTICS",
    "space": "SPACE",
    "cybersecurity": "CYBER",
    "semiconductors": "SEMICON",
}

IMPORTANCE_ORDER = {"LEAD": 0, "EVIDENCE": 1, "CONTEXT": 2, "WATCH": 3}


def loc_id(city: str, country: str) -> str:
    raw = f"{city}-{country}".lower()
    return "".join(c if c.isalnum() else "-" for c in raw).strip("-")


def dashboard_data(data: dict) -> dict:
    """Derive the homepage console dataset from the published network.

    Everything in this file is computed from network.json records - no
    hand-maintained duplicates, no synthetic telemetry.
    """
    signals = sorted(
        data["signals"],
        key=lambda s: (s["published"], -IMPORTANCE_ORDER.get(s.get("importance", ""), 9)),
        reverse=True,
    )
    briefings = data["briefings"]
    topics = index_by(data["topics"])
    entities = index_by(data["entities"])

    sig_items = [
        {
            "id": s["id"],
            "slug": s["slug"],
            "url": f"/signals/{s['slug']}/",
            "title": s["title"],
            "deck": s["deck"],
            "published": s["published"],
            "updated": s.get("updated") or s["published"],
            "status": s["status"],
            "importance": s.get("importance", ""),
            "topics": s.get("topics", []),
            "entities": s.get("entities", []),
            "briefings": s.get("related_briefings", []),
            "sources": [ref["id"] for ref in s.get("sources", [])],
        }
        for s in signals
    ]

    topic_items = []
    for t in data["topics"]:
        t_sigs = [s for s in data["signals"] if t["id"] in s.get("topics", [])]
        t_briefs = [b for b in briefings if t["id"] in b.get("topics", [])]
        topic_items.append(
            {
                "id": t["id"],
                "slug": t["slug"],
                "name": t["name"],
                "short": TOPIC_SHORT.get(t["id"], t["name"].upper()),
                "status": t["status"],
                "url": f"/topics/{t['slug']}/",
                "signals": len(t_sigs),
                "briefings": len(t_briefs),
            }
        )

    ent_items = []
    for ent in data["entities"]:
        e_sigs = [s["id"] for s in data["signals"] if ent["id"] in s.get("entities", [])]
        e_briefs = [b["id"] for b in briefings if ent["id"] in b.get("entities", [])]
        ent_items.append(
            {
                "id": ent["id"],
                "slug": ent["slug"],
                "name": ent["name"],
                "type": ent["type"],
                "status": ent["status"],
                "url": f"/entities/{ent['slug']}/",
                "signals": e_sigs,
                "briefings": e_briefs,
                "location": ent.get("location"),
            }
        )

    loc_groups: dict[tuple[str, str], dict] = {}
    for ent in data["entities"]:
        loc = ent.get("location")
        if not loc:
            continue
        key = (loc["city"], loc["country"])
        group = loc_groups.setdefault(
            key,
            {
                "id": loc_id(loc["city"], loc["country"]),
                "name": loc["name"],
                "city": loc["city"],
                "country": loc["country"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "basis": loc.get("basis", ""),
                "entity_ids": [],
            },
        )
        group["entity_ids"].append(ent["id"])

    loc_items = []
    for key in sorted(loc_groups, key=lambda k: loc_groups[k]["name"]):
        group = loc_groups[key]
        loc_sigs = []
        loc_briefs = []
        for ent_id in group["entity_ids"]:
            for s in signals:
                if ent_id in s.get("entities", []) and s["id"] not in loc_sigs:
                    loc_sigs.append(s["id"])
            for b in briefings:
                if ent_id in b.get("entities", []) and b["id"] not in [x["id"] for x in loc_briefs]:
                    loc_briefs.append(
                        {"id": b["id"], "title": b["title"], "url": f"/briefings/{b['slug']}/"}
                    )
        loc_topics = []
        for s in signals:
            if s["id"] in loc_sigs:
                for tid in s.get("topics", []):
                    if tid not in loc_topics:
                        loc_topics.append(tid)
        latest = next((s for s in signals if s["id"] in loc_sigs), None)
        loc_items.append(
            {
                **group,
                "entities": [
                    {"id": ent_id, "name": entities[ent_id]["name"], "type": entities[ent_id]["type"], "url": f"/entities/{entities[ent_id]['slug']}/"}
                    for ent_id in group["entity_ids"]
                ],
                "signals": loc_sigs,
                "briefings": loc_briefs,
                "signal_count": len(loc_sigs),
                "topics": loc_topics,
                "latest": (
                    {
                        "id": latest["id"],
                        "title": latest["title"],
                        "url": f"/signals/{latest['slug']}/",
                        "published": latest["published"],
                        "status": latest["status"],
                    }
                    if latest
                    else None
                ),
            }
        )

    unmapped = [
        {"id": ent["id"], "name": ent["name"], "type": ent["type"]}
        for ent in data["entities"]
        if not ent.get("location")
    ]

    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str], dict] = {}

    def node(key: str, label: str, kind: str, url: str, status: str = "") -> None:
        nodes.setdefault(key, {"id": key, "label": label, "kind": kind, "url": url, "status": status, "weight": 0})

    def edge(a: str, b: str) -> None:
        if a == b:
            return
        pair = (a, b) if a < b else (b, a)
        edges.setdefault(pair, {"source": pair[0], "target": pair[1], "weight": 0})
        edges[pair]["weight"] += 1

    for t in data["topics"]:
        node(f"topic:{t['id']}", TOPIC_SHORT.get(t["id"], t["name"].upper()), "topic", f"/topics/{t['slug']}/", t["status"])
    for ent in data["entities"]:
        node(f"entity:{ent['id']}", ent["name"].upper(), "entity", f"/entities/{ent['slug']}/", ent["status"])
    for b in briefings:
        node(f"briefing:{b['id']}", b["title"].upper(), "briefing", f"/briefings/{b['slug']}/", b["status"])

    records = list(data["signals"]) + list(briefings)
    for rec in records:
        rec_topics = [f"topic:{t}" for t in rec.get("topics", []) if t in topics]
        rec_entities = [f"entity:{en}" for en in rec.get("entities", []) if en in entities]
        for key in rec_topics + rec_entities:
            if key in nodes:
                nodes[key]["weight"] += 1
        for a in rec_entities:
            for b_ in rec_topics:
                edge(a, b_)
        for i, a in enumerate(rec_entities):
            for b_ in rec_entities[i + 1 :]:
                edge(a, b_)
        for i, a in enumerate(rec_topics):
            for b_ in rec_topics[i + 1 :]:
                edge(a, b_)
        if rec in briefings:
            bkey = f"briefing:{rec['id']}"
            nodes[bkey]["weight"] += len(rec.get("related_signals", [])) or 1
            for tkey in rec_topics:
                edge(bkey, tkey)
            for ekey in rec_entities:
                edge(bkey, ekey)

    by_day: dict[str, int] = {}
    for s in data["signals"]:
        by_day[s["published"]] = by_day.get(s["published"], 0) + 1

    source_counts: dict[str, int] = {}
    for s in data["signals"]:
        for ref in s.get("sources", []):
            source_counts[ref["id"]] = source_counts.get(ref["id"], 0) + 1
    sources_by_id = index_by(data["sources"])
    cited = [
        {"id": sid, "name": sources_by_id.get(sid, {}).get("name", sid), "count": n}
        for sid, n in sorted(source_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    status_counts: dict[str, int] = {}
    for s in data["signals"]:
        status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1

    inbox_count = 0
    if RSS_INBOX_PATH.exists():
        try:
            inbox_count = len(json.loads(RSS_INBOX_PATH.read_text(encoding="utf-8")).get("items", []))
        except (ValueError, OSError):
            inbox_count = 0

    lead = briefings and index_by(briefings, "slug").get(data["site"]["edition"].get("lead_briefing", ""))

    voxel_countries: dict[str, dict] = {}
    if VOXEL_COUNTRIES_PATH.is_file():
        try:
            voxel_payload = json.loads(VOXEL_COUNTRIES_PATH.read_text(encoding="utf-8"))
            voxel_countries = {c["id"]: c for c in voxel_payload.get("countries", [])}
        except (OSError, ValueError):
            voxel_countries = {}

    country_items = country_records(
        loc_items=loc_items,
        entities=entities,
        signals=signals,
        voxel_countries=voxel_countries,
    )
    world_countries = world_country_registry(voxel_countries)

    intel_store = IntelligenceStore()
    intel_events = intel_store.latest_events(limit=500)
    intel_articles = intel_store.articles()
    country_intel_events = country_event_summary(intel_events)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "edition": data["site"]["edition"],
            "counts": {
                "signals": len(data["signals"]),
                "briefings": len(briefings),
                "topics": len(data["topics"]),
                "entities": len(data["entities"]),
                "entities_mapped": len(data["entities"]) - len(unmapped),
                "sources": len(data["sources"]),
                "sources_cited": len(source_counts),
                "collections": len(data["collections"]),
                "inbox": inbox_count,
                "countries_with_presence": len(country_items),
                "world_countries": len(voxel_countries),
                "intel_events": len(intel_events),
                "intel_articles": len(intel_articles),
                "countries_with_events": len(country_intel_events),
            },
            "lead_briefing": data["site"]["edition"].get("lead_briefing"),
        },
        "topics": topic_items,
        "signals": sig_items,
        "entities": ent_items,
        "locations": loc_items,
        "countries": country_items,
        "world_countries": world_countries,
        "unmapped_entities": unmapped,
        "graph": {"nodes": list(nodes.values()), "edges": list(edges.values())},
        "charts": {
            "signals_by_topic": [
                {"id": t["id"], "name": TOPIC_SHORT.get(t["id"], t["name"].upper()), "count": t["signals"]}
                for t in topic_items
            ],
            "signals_by_status": [{"status": k, "count": v} for k, v in sorted(status_counts.items())],
            "signals_by_day": [{"date": d, "count": c} for d, c in sorted(by_day.items())],
            "sources_cited": cited,
        },
        "timeline": (lead or {}).get("timeline", []),
        "intel_events": intel_events,
        "intel_articles": intel_articles[:120],
        "country_intel_events": country_intel_events,
    }


def homepage(data: dict) -> str:
    site = data["site"]
    briefings = index_by(data["briefings"], "slug")
    lead = briefings[site["edition"]["lead_briefing"]]
    topics = {t["id"]: t for t in data["topics"]}
    entities = {t["id"]: t for t in data["entities"]}
    signals = sorted(
        data["signals"],
        key=lambda s: (s["published"], -IMPORTANCE_ORDER.get(s.get("importance", ""), 9)),
        reverse=True,
    )
    lab_projects = data["lab"]["projects"][:2]
    crumb = [("/", "Home")]
    dash = dashboard_data(data)
    counts = dash["meta"]["counts"]
    enabled_source_count = len(load_sources())

    topic_chips = "".join(
        f'<button type="button" class="f-chip" data-topic="{e(t["id"])}">{e(TOPIC_SHORT.get(t["id"], t["name"].upper()))}</button>'
        for t in data["topics"]
    )

    event_rows = []
    for ev in dash.get("intel_events", [])[:24]:
        fact = ev["facts"][0] if ev.get("facts") else ev.get("event_type", "event")
        sectors = " · ".join(e(s.upper()) for s in ev.get("sectors", [])[:3]) or "UNCLASSIFIED"
        prov = ev.get("provenance") or {}
        src_url = prov.get("canonical_url", "#")
        event_rows.append(
            f"""<article class="evt-row">
  <div class="evt-flag"><b>{e(ev.get("event_type", "event").replace("_", " ").upper())}</b><time datetime="{e(ev.get("timestamp", ""))}">{e(short_date(ev.get("timestamp", "")[:10])) if ev.get("timestamp") else "—"}</time></div>
  <div class="evt-body">
    <h3><a href="{e(src_url)}" rel="noopener noreferrer">{e(fact[:120])}</a></h3>
    <p class="evt-meta">{sectors} // {e(ev.get("confidence", "medium").upper())} // {e(prov.get("source_name", ""))}</p>
  </div>
</article>"""
        )
    events_html = "".join(event_rows) if event_rows else (
        '<div class="data-state"><strong>NO EXTRACTED EVENTS</strong>'
        "<p>Run the ingestion pipeline to populate the editorial inbox and event layer.</p></div>"
    )

    sector_chips = "".join(
        f'<button type="button" class="f-chip info-sector-chip" data-sector="{e(sid)}">{e(label.upper())}</button>'
        for sid, label in SECTOR_LABELS.items()
    )
    info_rows = []
    for art in dash.get("intel_articles", [])[:80]:
        sectors = art.get("suggested_topics") or []
        primary = art.get("primary_sector") or "general"
        sector_label = primary_sector_label(primary) if primary != "general" else "GENERAL"
        pub = art.get("published_at") or art.get("ingested_at") or ""
        info_rows.append(
            f"""<article class="info-row" data-sectors="{e(",".join(sectors))}" data-primary="{e(primary)}">
  <div class="info-flag"><b>{e(sector_label)}</b><time datetime="{e(pub)}">{e(short_date(pub[:10])) if pub else "—"}</time></div>
  <div class="info-body">
    <h3><a href="{e(art["canonical_url"])}" rel="noopener noreferrer">{e(art["title"][:140])}</a></h3>
    <p class="info-meta">{e(art.get("source", ""))} // {e(art.get("source_reliability") or art.get("source_category") or "source")} // INBOX</p>
  </div>
</article>"""
        )
    info_stream_html = "".join(info_rows) if info_rows else (
        '<div class="data-state"><strong>NO INGESTED ARTICLES</strong><p>Run make ingest to populate the information stream.</p></div>'
    )

    sig_rows = []
    for s in signals:
        sig_topics = [t for t in s.get("topics", []) if t in topics]
        topic_line = " · ".join(e(TOPIC_SHORT.get(t, topics[t]["name"].upper())) for t in sig_topics)
        sig_rows.append(
            f"""<article class="sig-row" data-sid="{e(s["id"])}" data-topics="{e(",".join(sig_topics))}" data-published="{e(s["published"])}" data-status="{e(s["status"])}">
  <div class="sig-flag"><b class="flag-{e(s["status"].lower())}">{e(s["status"])}</b><time datetime="{e(s["published"])}">{e(short_date(s["published"]))}</time></div>
  <div class="sig-body">
    <h3><a href="/signals/{e(s["slug"])}/" data-track="signal">{e(s["title"])}</a></h3>
    <p class="sig-topics">{topic_line} // {e(s.get("importance", ""))}</p>
  </div>
</article>"""
        )

    status_bars = bar_rows(
        [(item["status"], item["count"], None, item["status"]) for item in dash["charts"]["signals_by_status"]],
        "chart-status",
        "data-status",
    )
    topic_bars = bar_rows(
        [
            (t["name"], t["signals"], t["url"], t["id"])
            for t in dash["topics"]
        ],
        "chart-topics",
        "data-topic",
    )
    landscape_topic_bars = bar_rows(
        [(t["name"], t["signals"], t["url"], t["id"]) for t in dash["topics"]],
        "chart-landscape",
        "data-topic",
    )
    source_bars = bar_rows(
        [(s["name"], s["count"], None, s["id"]) for s in dash["charts"]["sources_cited"]],
        "chart-sources",
        "data-source",
    )
    landscape_status_bars = bar_rows(
        [
            ("VERIFIED", sum(1 for s in signals if s["status"] == "VERIFIED"), None, "VERIFIED"),
            ("REPORTED", sum(1 for s in signals if s["status"] == "REPORTED"), None, "REPORTED"),
        ],
        "chart-landscape-status",
        "data-status",
    )

    days = dash["charts"]["signals_by_day"]
    if len(days) >= 3:
        top_day = max(d["count"] for d in days)
        day_bars = "".join(
            f'<div class="day-col" title="{e(d["date"])}: {d["count"]} signals">'
            f'<span class="day-fill" style="height:{max(8, round(100 * d["count"] / top_day))}%"></span>'
            f'<span class="day-label">{e(short_date(d["date"]))}</span></div>'
            for d in days
        )
        trend_html = f'<div class="day-chart" id="chart-trend">{day_bars}</div>'
    else:
        day_list = "".join(
            f"<li><b>{e(short_date(d['date']))}</b> - {d['count']} signal{'s' if d['count'] != 1 else ''}</li>"
            for d in days
        )
        trend_html = f"""<div class="data-state" id="chart-trend">
  <strong>BUILDING DATASET</strong>
  <p>{counts["signals"]} signals across {len(days)} day{"s" if len(days) != 1 else ""} of published coverage. The trend view unlocks when the record spans more days - no synthetic history is drawn.</p>
  <ul>{day_list}</ul>
</div>"""

    top_edges = sorted(dash["graph"]["edges"], key=lambda x: -x["weight"])[:6]
    node_labels = {n["id"]: n["label"] for n in dash["graph"]["nodes"]}
    top_links = "".join(
        f'<li><span>{e(node_labels.get(ed["source"], ed["source"]))}</span><i>↔</i><span>{e(node_labels.get(ed["target"], ed["target"]))}</span><b>{ed["weight"]} REC</b></li>'
        for ed in top_edges
    )

    body = f"""
<section class="masthead container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">INFORMATION NETWORK // STATIC-FIRST</p>
  <h1>THE<br><span>TECH BRIEFING.</span></h1>
  <p class="masthead-deck">{e(site["tagline"])}</p>
  <div class="loop-row">{' <span>→</span> '.join(e(step) for step in site["loop"])}</div>
</section>

<section class="console container" id="console">
  <div class="console-head">
    <p class="ed-label">01 / NETWORK CONSOLE</p>
    <p class="console-sub">A live control surface over the published record. Every panel is derived from the information network - no synthetic telemetry, no invented activity.</p>
    <div class="filter-bar" id="filter-bar" role="group" aria-label="Information filters">
      <span class="filter-group" role="group" aria-label="Topic filter">
        <span class="filter-label">TOPIC</span>
        <button type="button" class="f-chip is-active" data-topic="all">ALL</button>
        {topic_chips}
      </span>
      <span class="filter-group" role="group" aria-label="Time window filter">
        <span class="filter-label">WINDOW</span>
        <button type="button" class="f-chip" data-window="today">TODAY</button>
        <button type="button" class="f-chip" data-window="7d">7 DAYS</button>
        <button type="button" class="f-chip" data-window="30d">30 DAYS</button>
        <button type="button" class="f-chip is-active" data-window="all">ALL TIME</button>
      </span>
      <span class="filter-readout" id="filter-readout">{counts["signals"]} / {counts["signals"]} SIGNALS IN VIEW</span>
    </div>
  </div>

  <div class="panel" id="panel-map">
    <div class="panel-head"><span class="panel-title">NETWORK SNAPSHOT</span><span class="panel-note">PUBLISHED SIGNALS · FILTER AFFECTED</span></div>
    <div class="snapshot-grid">
      <div class="snapshot-main">
        <p class="mini-label">SIGNAL LANDSCAPE</p>
        {landscape_topic_bars}
        <p class="mini-label">VERIFICATION</p>
        <div class="verify-list" id="landscape-verify">{landscape_status_bars}</div>
      </div>
      <aside class="snapshot-side" aria-label="Current record summary">
        <p class="mini-label">CURRENT RECORD</p>
        <dl class="snapshot-stats">
          <div><dt>SIGNALS</dt><dd id="snapshot-signals">{counts["signals"]}</dd></div>
          <div><dt>TOPICS</dt><dd id="snapshot-topics">{counts["topics"]}</dd></div>
          <div><dt>SOURCES</dt><dd id="snapshot-sources">{counts["sources_cited"]}</dd></div>
          <div><dt>VERIFIED</dt><dd id="snapshot-verified">{sum(1 for s in signals if s["status"] == "VERIFIED")}</dd></div>
          <div><dt>REPORTED</dt><dd id="snapshot-reported">{sum(1 for s in signals if s["status"] == "REPORTED")}</dd></div>
        </dl>
      </aside>
    </div>
    <p class="panel-foot">Signal distribution is derived from published records only. No synthetic activity is added.</p>
  </div>

  <div class="panel" id="panel-events">
    <div class="panel-head"><span class="panel-title">EXTRACTED EVENTS</span><span class="panel-note">{counts.get("intel_events", 0)} FROM INGEST · INBOX ONLY</span></div>
    <div class="evt-list">{events_html}</div>
    <p class="panel-foot">Structured events from ingested sources. Facts are separated from interpretation. Nothing here is published or traded. <a href="/intelligence/">Open intelligence layer</a></p>
  </div>

  <div class="panel" id="panel-info-stream">
    <div class="panel-head"><span class="panel-title">INFORMATION STREAM</span><span class="panel-note">{counts.get("intel_articles", 0)} ARTICLES · EDITORIAL INBOX</span></div>
    <div class="filter-bar info-filter-bar" role="group" aria-label="Sector filter">
      <span class="filter-group">
        <span class="filter-label">SECTOR</span>
        <button type="button" class="f-chip info-sector-chip is-active" data-sector="all">ALL</button>
        {sector_chips}
      </span>
      <span class="filter-readout" id="info-stream-readout">{counts.get("intel_articles", 0)} IN VIEW</span>
    </div>
    <div class="info-list" id="info-stream">{info_stream_html}</div>
    <p class="panel-foot">Live ingested information from {enabled_source_count} sources. Items remain in INBOX until editorially promoted to a published signal or briefing.</p>
  </div>

  <div class="console-grid">
    <div class="panel" id="panel-signals">
      <div class="panel-head"><span class="panel-title">CURRENT SIGNALS</span><span class="panel-note" id="signals-count">{counts["signals"]} RECORDS</span></div>
      <div class="sig-list" id="sig-list">
        {"".join(sig_rows)}
      </div>
      <p class="panel-foot"><a href="/signals/">Open the full signal index</a> · <a href="/briefings/">Briefings</a></p>
    </div>

    <div class="panel" id="panel-status">
      <div class="panel-head"><span class="panel-title">SYSTEM STATUS</span><span class="panel-note">NETWORK SNAPSHOT</span></div>
      <dl class="stat-list">
        <div><dt>EDITION</dt><dd>{e(site["edition"]["id"])} // <b class="ok">{e(site["edition"]["status"])}</b></dd></div>
        <div><dt>SIGNALS</dt><dd id="stat-signals">{counts["signals"]} PUBLISHED</dd></div>
        <div><dt>BRIEFINGS</dt><dd>{counts["briefings"]} PUBLISHED</dd></div>
        <div><dt>TOPICS</dt><dd>{counts["topics"]} TRACKED</dd></div>
        <div><dt>ENTITIES</dt><dd>{counts["entities"]} REGISTERED · {counts["entities_mapped"]} MAPPED</dd></div>
        <div><dt>SOURCES</dt><dd>{counts["sources"]} REGISTERED · {counts["sources_cited"]} CITED</dd></div>
        <div><dt>INGEST INBOX</dt><dd>{counts["inbox"]} HELD FOR REVIEW</dd></div>
        <div><dt>EXTRACTED EVENTS</dt><dd>{counts.get("intel_events", 0)} IN EVENT LAYER</dd></div>
        <div><dt>UPDATED</dt><dd>{e(pretty_date(site["edition"]["date"]))}</dd></div>
      </dl>
      <p class="mini-label">SIGNAL VERIFICATION SPLIT</p>
      {status_bars}
    </div>
  </div>

  <div class="console-grid three">
    <div class="panel" id="panel-topics">
      <div class="panel-head"><span class="panel-title">TOPIC ACTIVITY</span><span class="panel-note">SIGNALS PER TOPIC</span></div>
      {topic_bars}
      <p class="panel-foot">Select a bar to filter the console by topic.</p>
    </div>
    <div class="panel" id="panel-trend">
      <div class="panel-head"><span class="panel-title">SIGNALS OVER TIME</span><span class="panel-note">PUBLISHED PER DAY</span></div>
      {trend_html}
    </div>
    <div class="panel" id="panel-sources">
      <div class="panel-head"><span class="panel-title">SOURCE DISTRIBUTION</span><span class="panel-note">CITATIONS IN SIGNALS</span></div>
      {source_bars}
      <p class="panel-foot">{counts["sources"]} sources registered. Uncited sources stay at zero until a published record references them.</p>
    </div>
  </div>

  <div class="panel" id="panel-net">
    <div class="panel-head"><span class="panel-title">RELATIONSHIP NETWORK</span><span class="panel-note">{len(dash["graph"]["nodes"])} NODES · {len(dash["graph"]["edges"])} EDGES FROM THE RECORD</span></div>
    <div class="net-grid">
      <div class="net-stage">
        <canvas id="net-canvas" aria-label="Relationship network of topics, entities and briefings"></canvas>
        <div class="net-legend" aria-hidden="true"><span class="lg-topic">■ TOPIC</span><span class="lg-entity">● ENTITY</span><span class="lg-briefing">◆ BRIEFING</span></div>
      </div>
      <aside class="net-detail" id="net-detail">
        <p class="mini-label">TOP CONNECTIONS</p>
        <ul class="top-links">{top_links}</ul>
        <p class="detail-hint">SELECT A NODE TO INSPECT ITS RECORD.</p>
      </aside>
    </div>
    <p class="panel-foot">Nodes are published records (topics, entities, briefings). Edges are real co-occurrence inside signals and briefings - nothing is drawn without a record behind it.</p>
  </div>
</section>

<section class="ed-section container" id="lead">
  <p class="ed-label">02 / LEAD BRIEFING</p>
  <div class="lead">
    <div>
      <p class="lead-kicker">{e(lead.get("kicker", "LEAD"))}</p>
      <h2><a href="/briefings/{e(lead["slug"])}/" data-track="briefing">{e(lead["title"])}</a></h2>
      <p class="lead-deck">{e(lead["deck"])}</p>
      <p class="lead-cta"><a class="console-cta" href="/briefings/{e(lead["slug"])}/" data-track="briefing">READ FULL BRIEFING →</a></p>
    </div>
    <dl class="meta-col">
      <dt>PUBLISHED</dt><dd>{e(pretty_date(lead["published"]))}</dd>
      <dt>STATUS</dt><dd>{e(lead["status"])}</dd>
      <dt>TOPICS</dt><dd>{", ".join(e(topics[t]["name"]) for t in lead["topics"] if t in topics)}</dd>
      <dt>VERIFY</dt><dd><a href="/briefings/{e(lead["slug"])}/#sources">Primary + independent sources</a></dd>
    </dl>
  </div>
</section>
<section class="ed-section container" id="why">
  <p class="ed-label">03 / WHY THIS MATTERS</p>
  {numbered(lead["why_it_matters"][:4])}
</section>
<section class="ed-section container" id="topics">
  <p class="ed-label">04 / TOPIC PULSE</p>
  <table class="pulse-table">
    <thead><tr><th>TOPIC</th><th>STATUS</th><th>NOW</th></tr></thead>
    <tbody>
      {"".join(f'<tr><td><a href="/topics/{e(t["slug"])}/">{e(t["name"])}</a></td><td class="status">{e(t["status"])}</td><td><p>{e(t["current_status"])}</p></td></tr>' for t in data["topics"])}
    </tbody>
  </table>
</section>
<section class="ed-section container" id="timeline">
  <p class="ed-label">05 / DEVELOPING STORY</p>
  <ul class="timeline" id="story-timeline">
    {"".join(f'<li data-date="{e(ev["date"])}"><time datetime="{e(ev["date"])}">{e(ev["date"])}</time><strong>{e(ev["label"])}</strong><p>{e(ev["text"])}</p></li>' for ev in lead["timeline"])}
  </ul>
</section>
<section class="ed-section container" id="connected">
  <p class="ed-label">06 / CONNECTED INFORMATION</p>
  <div class="connected-grid">
    <div>
      <h3>ENTITIES</h3>
      <ul>{"".join(f'<li><a href="/entities/{e(entities[i]["slug"])}/">{e(entities[i]["name"])}</a></li>' for i in lead["entities"] if i in entities)}</ul>
    </div>
    <div>
      <h3>COLLECTION</h3>
      <ul>{"".join(f'<li><a href="/collections/{e(c["slug"])}/">{e(c["name"])}</a></li>' for c in data["collections"])}</ul>
    </div>
    <div>
      <h3>SOURCES</h3>
      <ul>{"".join(f'<li><a href="{e(s["url"])}" rel="noopener noreferrer">{e(s["title"])}</a></li>' for s in lead["sources"])}</ul>
    </div>
  </div>
</section>
<section class="ed-section container" id="lab">
  <p class="ed-label">07 / LATEST FROM THE LAB</p>
  <div class="row-list">
    {"".join(row(f"<b>{e(p['code'])}</b><br>{e(p['status'])}", p["title"], "/lab/projects/", p["summary"], "LAB") for p in lab_projects)}
  </div>
  <p class="lead-meta" style="margin-top:18px"><a href="/lab/" data-track="lab">Open the Lab layer</a> · <a href="/lab/experiments/xeno-signal/" data-track="lab">Xeno Signal experiment</a></p>
</section>
<section class="ed-section container" id="method">
  <p class="ed-label">08 / SOURCES AND METHOD</p>
  <div class="method-block">
    <div>
      <p>RSS is an inbox, not the product. Headlines are ingested, normalized, validated, and held at editorial_state=INBOX with publish=false until a briefing or signal is written against primary sources.</p>
      <p>This edition’s lead briefing is sourced to Anthropic’s 27 August 2026 announcement plus independent reports from Ars Technica and CNBC. Partner anecdotes that exist only in the vendor post are labeled REPORTED, not VERIFIED.</p>
    </div>
    <div class="pipeline">{' <span>→</span> '.join(e(step) for step in site["pipeline"])}</div>
  </div>
</section>
"""
    ld = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site["name"],
            "url": site["url"],
            "description": site["description"],
            "potentialAction": {
                "@type": "SearchAction",
                "target": site["url"] + "/search/?q={query}",
                "query-input": "required name=query",
            },
        },
        crumb_ld(site, crumb),
    ]
    return layout(
        data,
        title=f'{site["name"]} — {site["tagline"]}',
        description=site["description"],
        route="/",
        active="home",
        body=body,
        crumbs=crumb,
        extra_css=["/css/dashboard.css"],
        extra_js=["/js/dashboard.js", "/js/info-stream.js"],
        ld=ld,
    )


def briefings_index(data: dict) -> str:
    crumb = [("/", "Home"), ("/briefings/", "Briefings")]
    rows = "".join(
        row(
            f"<b>{e(b['status'])}</b><br>{e(pretty_date(b['published']))}",
            b["title"],
            f"/briefings/{b['slug']}/",
            b["deck"],
        )
        for b in sorted(data["briefings"], key=lambda x: x["published"], reverse=True)
    )
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">UNDERSTAND</p>
  <h1>BRIEFINGS<span>.</span></h1>
  <p>Authored, sourced explainers. A briefing is not a headline and not an RSS item. It has to survive VERIFY.</p>
</section>
<section class="ed-section container"><div class="row-list">{rows}</div></section>
"""
    return layout(
        data,
        title="Briefings — The Tech Briefing",
        description="Authored briefings from The Tech Briefing information network.",
        route="/briefings/",
        active="briefings",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def briefing_page(data: dict, briefing: dict) -> str:
    topics = index_by(data["topics"])
    entities = index_by(data["entities"])
    signals = index_by(data["signals"])
    crumb = [("/", "Home"), ("/briefings/", "Briefings"), (f"/briefings/{briefing['slug']}/", briefing["title"])]
    history = briefing.get("history") or []
    related_sigs = [signals[i] for i in briefing.get("related_signals", []) if i in signals]
    watch = "".join(
        f"<li><b>→</b><span><strong>{e(w['item'])}</strong> {e(w['why'])}</span></li>"
        for w in briefing.get("watch_next", [])
    )
    body = f"""
<article class="container article-head">
  {breadcrumbs(crumb)}
  <p class="lead-kicker">{e(briefing.get("kicker", "BRIEFING"))}</p>
  <h1>{e(briefing["title"])}</h1>
  <p class="article-deck">{e(briefing["deck"])}</p>
  <div class="article-byline">
    <span>PUBLISHED <b>{e(pretty_date(briefing["published"]))}</b></span>
    <span>UPDATED <b>{e(pretty_date(briefing.get("updated")))}</b></span>
    <span>STATUS <b>{e(briefing["status"])}</b></span>
  </div>
</article>
<div class="container briefing-layout">
  <div class="briefing-body">
    <h2 id="takeaways">Key takeaways</h2>
    {numbered(briefing["takeaways"])}
    <h2 id="happened">What happened</h2>
    {numbered(briefing["what_happened"])}
    <h2 id="why">Why it matters</h2>
    {numbered(briefing["why_it_matters"])}
    <h2 id="context">Context</h2>
    {numbered(briefing["context"])}
    <h2 id="timeline">Timeline</h2>
    <ul class="timeline">{"".join(f'<li><time datetime="{e(ev["date"])}">{e(ev["date"])}</time><strong>{e(ev["label"])}</strong><p>{e(ev["text"])}</p></li>' for ev in briefing["timeline"])}</ul>
    <h2 id="map">Entities, topics, sources</h2>
    <p>Topics {chips("topics", briefing["topics"], topics)}</p>
    <p>Entities {chips("entities", briefing["entities"], entities)}</p>
    <div id="sources">{source_rows(data, briefing["sources"])}</div>
    <h2 id="related">Related signals</h2>
    <div class="row-list">{"".join(row(f"<b>{e(s['status'])}</b><br>{e(pretty_date(s['published']))}", s["title"], f"/signals/{s['slug']}/", s["deck"]) for s in related_sigs) or empty("NONE YET", "No related signals attached.")}</div>
    <h2 id="watch">What to watch next</h2>
    <ul class="watch-list">{watch}</ul>
    <h2 id="history">Correction / update history</h2>
    <ul class="timeline">{"".join(f'<li><time datetime="{e(h["date"])}">{e(pretty_date(h["date"]))}</time><strong>{e(h["type"].upper())}</strong><p>{e(h["text"])}</p></li>' for h in history) or "<li><p>No corrections issued.</p></li>"}</ul>
  </div>
  <aside class="rail" aria-label="Briefing metadata">
    <h2>RECORD</h2>
    <ul>
      <li>ID {e(briefing["id"])}</li>
      <li>{e(briefing["status"])}</li>
      <li>Edition {e(data["site"]["edition"]["id"])}</li>
    </ul>
    <h2>ON THIS PAGE</h2>
    <ul>
      <li><a href="#takeaways">Takeaways</a></li>
      <li><a href="#happened">What happened</a></li>
      <li><a href="#why">Why it matters</a></li>
      <li><a href="#context">Context</a></li>
      <li><a href="#timeline">Timeline</a></li>
      <li><a href="#sources">Sources</a></li>
      <li><a href="#watch">Watch next</a></li>
    </ul>
    <h2>COLLECTION</h2>
    <ul>{"".join(f'<li><a href="/collections/{e(c)}/">{e(c)}</a></li>' for c in briefing.get("related_collections", []))}</ul>
  </aside>
</div>
"""
    article_ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": briefing["title"],
        "description": briefing["deck"],
        "datePublished": briefing["published"],
        "dateModified": briefing.get("updated") or briefing["published"],
        "mainEntityOfPage": data["site"]["url"] + f"/briefings/{briefing['slug']}/",
        "author": {"@type": "Person", "name": data["site"]["author"]["name"]},
        "publisher": {"@type": "Organization", "name": data["site"]["name"], "url": data["site"]["url"]},
    }
    return layout(
        data,
        title=f'{briefing["title"]} — The Tech Briefing',
        description=briefing["deck"],
        route=f"/briefings/{briefing['slug']}/",
        active="briefings",
        body=body,
        crumbs=crumb,
        og_type="article",
        article=briefing,
        ld=[article_ld, crumb_ld(data["site"], crumb)],
    )


def signals_index(data: dict) -> str:
    crumb = [("/", "Home"), ("/signals/", "Signals")]
    rows = "".join(
        row(
            f"<b>{e(s['status'])}</b><br>{e(pretty_date(s['published']))}",
            s["title"],
            f"/signals/{s['slug']}/",
            s["deck"],
        )
        for s in sorted(data["signals"], key=lambda x: x["published"], reverse=True)
    )
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">READ</p>
  <h1>SIGNALS<span>.</span></h1>
  <p>Curated, source-backed observations. The RSS inbox is not shown here. Ingested headlines stay unpublished until editorial review.</p>
</section>
<section class="ed-section container"><div class="row-list">{rows}</div></section>
"""
    return layout(
        data,
        title="Signals — The Tech Briefing",
        description="Curated signals from The Tech Briefing. RSS ingest is not auto-published.",
        route="/signals/",
        active="signals",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def signal_page(data: dict, signal: dict) -> str:
    topics = index_by(data["topics"])
    entities = index_by(data["entities"])
    briefings = index_by(data["briefings"])
    crumb = [("/", "Home"), ("/signals/", "Signals"), (f"/signals/{signal['slug']}/", signal["title"])]
    related_brief = [briefings[i] for i in signal.get("related_briefings", []) if i in briefings]
    body = f"""
<article class="container article-head">
  {breadcrumbs(crumb)}
  <p class="lead-kicker">SIGNAL // {e(signal["importance"])}</p>
  <h1>{e(signal["title"])}</h1>
  <p class="article-deck">{e(signal["deck"])}</p>
  <div class="article-byline">
    <span>PUBLISHED <b>{e(pretty_date(signal["published"]))}</b></span>
    <span>STATUS <b>{e(signal["status"])}</b></span>
  </div>
</article>
<section class="container briefing-layout">
  <div class="briefing-body">
    <h2>Summary</h2>
    <p>{e(signal["summary"])}</p>
    <h2>Read</h2>
    <p>{e(signal["body"])}</p>
    <h2>Topics and entities</h2>
    {chips("topics", signal["topics"], topics)}
    {chips("entities", signal["entities"], entities)}
    <h2 id="sources">Sources</h2>
    {source_rows(data, signal["sources"])}
    <h2>Related briefings</h2>
    <div class="row-list">{"".join(row(e(pretty_date(b["published"])), b["title"], f"/briefings/{b['slug']}/", b["deck"]) for b in related_brief) or empty("NONE", "No briefing attached yet.")}</div>
  </div>
  <aside class="rail">
    <h2>RECORD</h2>
    <ul>
      <li>ID {e(signal["id"])}</li>
      <li>{e(signal["status"])}</li>
      <li>{e(signal["importance"])}</li>
    </ul>
  </aside>
</section>
"""
    return layout(
        data,
        title=f'{signal["title"]} — The Tech Briefing',
        description=signal["deck"],
        route=f"/signals/{signal['slug']}/",
        active="signals",
        body=body,
        crumbs=crumb,
        og_type="article",
        article=signal,
        ld=[crumb_ld(data["site"], crumb)],
    )


def topics_index(data: dict) -> str:
    crumb = [("/", "Home"), ("/topics/", "Topics")]
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">CONNECT</p>
  <h1>TOPICS<span>.</span></h1>
  <p>Persistent subjects, not tags. Empty coverage is shown honestly.</p>
</section>
<section class="ed-section container">
  <table class="pulse-table">
    <thead><tr><th>TOPIC</th><th>STATUS</th><th>NOW</th></tr></thead>
    <tbody>{"".join(f'<tr><td><a href="/topics/{e(t["slug"])}/">{e(t["name"])}</a></td><td class="status">{e(t["status"])}</td><td><p>{e(t["current_status"])}</p></td></tr>' for t in data["topics"])}</tbody>
  </table>
</section>
"""
    return layout(
        data,
        title="Topics — The Tech Briefing",
        description="Persistent topic pages for The Tech Briefing information network.",
        route="/topics/",
        active="topics",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def topic_page(data: dict, topic: dict) -> str:
    crumb = [("/", "Home"), ("/topics/", "Topics"), (f"/topics/{topic['slug']}/", topic["name"])]
    sigs = [s for s in data["signals"] if topic["id"] in s.get("topics", [])]
    briefs = [b for b in data["briefings"] if topic["id"] in b.get("topics", [])]
    ents = []
    for item in sigs + briefs:
        for entity_id in item.get("entities", []):
            if entity_id not in ents:
                ents.append(entity_id)
    entities = index_by(data["entities"])
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">TOPIC // {e(topic["status"])}</p>
  <h1>{e(topic["name"].upper())}<span>.</span></h1>
  <p>{e(topic["summary"])}</p>
</section>
<section class="ed-section container">
  <p class="ed-label">CURRENT STATUS</p>
  <p>{e(topic["current_status"])}</p>
</section>
<section class="ed-section container">
  <p class="ed-label">LATEST SIGNALS</p>
  {('<div class="row-list">' + ''.join(row(f"<b>{e(s['status'])}</b><br>{e(pretty_date(s['published']))}", s['title'], f"/signals/{s['slug']}/", s['deck']) for s in sigs) + '</div>') if sigs else empty("NO SIGNALS YET", "This topic is being watched. Ingested RSS items are not shown until they pass editorial review.")}
</section>
<section class="ed-section container">
  <p class="ed-label">LATEST BRIEFINGS</p>
  {('<div class="row-list">' + ''.join(row(e(pretty_date(b["published"])), b["title"], f"/briefings/{b['slug']}/", b["deck"]) for b in briefs) + '</div>') if briefs else empty("NO BRIEFING YET", "Coverage is still building. A topic page without a briefing is intentional, not a missing template.")}
</section>
<section class="ed-section container">
  <p class="ed-label">ENTITIES</p>
  {chips("entities", ents, entities) or empty("NONE LINKED", "No published records attach an entity to this topic yet.")}
</section>
<section class="ed-section container">
  <p class="ed-label">WATCH</p>
  {numbered(topic.get("watch", []))}
</section>
"""
    return layout(
        data,
        title=f'{topic["name"]} — The Tech Briefing',
        description=topic["summary"],
        route=f"/topics/{topic['slug']}/",
        active="topics",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def entities_index(data: dict) -> str:
    crumb = [("/", "Home"), ("/entities/", "Entities")]
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">CONNECT</p>
  <h1>ENTITIES<span>.</span></h1>
  <p>Companies, institutions, and standards that records attach to. An entity page can exist before a briefing does.</p>
</section>
<section class="ed-section container">
  <div class="row-list">{"".join(row(f"<b>{e(ent['type'])}</b><br>{e(ent['status'])}", ent["name"], f"/entities/{ent['slug']}/", ent["summary"]) for ent in data["entities"])}</div>
</section>
"""
    return layout(
        data,
        title="Entities — The Tech Briefing",
        description="Entity index for The Tech Briefing information network.",
        route="/entities/",
        active="topics",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def entity_page(data: dict, entity: dict) -> str:
    crumb = [("/", "Home"), ("/entities/", "Entities"), (f"/entities/{entity['slug']}/", entity["name"])]
    sigs = [s for s in data["signals"] if entity["id"] in s.get("entities", [])]
    briefs = [b for b in data["briefings"] if entity["id"] in b.get("entities", [])]
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">{e(entity["type"].upper())} // {e(entity["status"])}</p>
  <h1>{e(entity["name"].upper())}<span>.</span></h1>
  <p>{e(entity["summary"])}</p>
</section>
<section class="ed-section container">
  <p class="ed-label">NOTES</p>
  <p>{e(entity.get("notes", ""))}</p>
</section>
<section class="ed-section container">
  <p class="ed-label">SIGNALS</p>
  {('<div class="row-list">' + ''.join(row(e(pretty_date(s["published"])), s["title"], f"/signals/{s["slug"]}/", s["deck"]) for s in sigs) + '</div>') if sigs else empty("NO SIGNALS", "This entity is registered so future coverage can attach. Nothing authored yet.")}
</section>
<section class="ed-section container">
  <p class="ed-label">BRIEFINGS</p>
  {('<div class="row-list">' + ''.join(row(e(pretty_date(b["published"])), b["title"], f"/briefings/{b["slug"]}/", b["deck"]) for b in briefs) + '</div>') if briefs else empty("NO BRIEFING", "Honest empty state: the architecture is here; the reporting is not.")}
</section>
"""
    return layout(
        data,
        title=f'{entity["name"]} — The Tech Briefing',
        description=entity["summary"],
        route=f"/entities/{entity['slug']}/",
        active="topics",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def collection_page(data: dict, collection: dict) -> str:
    crumb = [("/", "Home"), (f"/collections/{collection['slug']}/", collection["name"])]
    briefings = index_by(data["briefings"])
    signals = index_by(data["signals"])
    topics = index_by(data["topics"])
    entities = index_by(data["entities"])
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">COLLECTION // {e(collection["status"])}</p>
  <h1>{e(collection["name"].upper())}<span>.</span></h1>
  <p>{e(collection["summary"])}</p>
</section>
<section class="ed-section container">
  <p class="ed-label">BRIEFINGS</p>
  <div class="row-list">{"".join(row(e(pretty_date(briefings[i]["published"])), briefings[i]["title"], f"/briefings/{briefings[i]["slug"]}/", briefings[i]["deck"]) for i in collection["briefings"] if i in briefings)}</div>
</section>
<section class="ed-section container">
  <p class="ed-label">SIGNALS</p>
  <div class="row-list">{"".join(row(e(pretty_date(signals[i]["published"])), signals[i]["title"], f"/signals/{signals[i]["slug"]}/", signals[i]["deck"]) for i in collection["signals"] if i in signals)}</div>
</section>
<section class="ed-section container">
  <p class="ed-label">ATTACHED</p>
  {chips("topics", collection["topics"], topics)}
  {chips("entities", collection["entities"], entities)}
  <p>{e(collection.get("notes", ""))}</p>
</section>
"""
    return layout(
        data,
        title=f'{collection["name"]} — The Tech Briefing',
        description=collection["summary"],
        route=f"/collections/{collection['slug']}/",
        active="archive",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def archive_page(data: dict) -> str:
    crumb = [("/", "Home"), ("/archive/", "Archive")]
    items = []
    for briefing in data["briefings"]:
        items.append((briefing["published"], "BRIEFING", briefing["title"], f"/briefings/{briefing['slug']}/", briefing["deck"]))
    for signal in data["signals"]:
        items.append((signal["published"], "SIGNAL", signal["title"], f"/signals/{signal['slug']}/", signal["deck"]))
    items.sort(key=lambda x: x[0], reverse=True)
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">VERIFY / DISCOVER</p>
  <h1>ARCHIVE<span>.</span></h1>
  <p>Published records only. Inbox items never appear here.</p>
</section>
<section class="ed-section container">
  <div class="row-list">{"".join(row(f"<b>{e(kind)}</b><br>{e(pretty_date(date))}", title, href, summary) for date, kind, title, href, summary in items)}</div>
</section>
"""
    return layout(
        data,
        title="Archive — The Tech Briefing",
        description="Published briefings and signals, newest first.",
        route="/archive/",
        active="archive",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def search_page(data: dict, index_items: list[dict]) -> str:
    crumb = [("/", "Home"), ("/search/", "Search")]
    topics = "".join(f'<option value="{e(t["id"])}">{e(t["name"])}</option>' for t in data["topics"])
    sources = "".join(f'<option value="{e(s["id"])}">{e(s["name"])}</option>' for s in data["sources"])
    years = sorted({str(item.get("date", ""))[:4] for item in index_items if item.get("date")}, reverse=True)
    year_opts = "".join(f'<option value="{e(year)}">{e(year)}</option>' for year in years)
    static_rows = "".join(
        row(f"<b>{e(item['type'])}</b><br>{e(pretty_date(item.get('date')))}", item["title"], item["url"], item.get("summary", ""))
        for item in index_items
    )
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">DISCOVER</p>
  <h1>SEARCH<span>.</span></h1>
  <p>Client-side search over the generated index. The full published record list below remains crawlable without JavaScript.</p>
</section>
<section class="ed-section container search-panel">
  <form id="search-form" method="get" action="/search/">
    <input type="search" name="q" placeholder="Titles, summaries, topics, entities, sources" aria-label="Search query">
    <select name="type" aria-label="Type">
      <option value="">All types</option>
      <option value="briefing">Briefing</option>
      <option value="signal">Signal</option>
      <option value="topic">Topic</option>
      <option value="entity">Entity</option>
      <option value="collection">Collection</option>
      <option value="lab">Lab</option>
    </select>
    <select name="topic" aria-label="Topic"><option value="">All topics</option>{topics}</select>
    <select name="source" aria-label="Source"><option value="">All sources</option>{sources}</select>
    <select name="date" aria-label="Year"><option value="">All dates</option>{year_opts}</select>
    <button type="submit">FILTER</button>
  </form>
  <p class="search-count" id="search-count">{len(index_items)} PUBLISHED RECORDS</p>
  <div id="search-results" class="row-list"></div>
  <div id="search-related" class="related-block"></div>
</section>
<section class="ed-section container" id="search-static">
  <p class="ed-label">PUBLISHED INDEX</p>
  <div class="row-list">{static_rows}</div>
</section>
"""
    return layout(
        data,
        title="Search — The Tech Briefing",
        description="Search published briefings, signals, topics, entities, and lab records.",
        route="/search/",
        active="search",
        body=body,
        crumbs=crumb,
        extra_js=["/js/search.js"],
        ld=[crumb_ld(data["site"], crumb)],
    )


def about_page(data: dict) -> str:
    site = data["site"]
    crumb = [("/", "Home"), ("/about/", "About")]
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">VERIFY</p>
  <h1>ABOUT THE<br><span>NETWORK.</span></h1>
  <p>{e(site["description"])}</p>
</section>
<section class="ed-section container">
  <p class="ed-label">WHAT THIS IS</p>
  <p>The Tech Briefing is an information network organized around READ → UNDERSTAND → VERIFY → CONNECT → DISCOVER. It is not a personal homepage, not a generic news site, and not an AI summary feed.</p>
  <p>The Lab is the retained portfolio of {e(site["author"]["name"])}: systems work, hardware, references, and experiments including Xeno Signal. It is a secondary layer.</p>
</section>
<section class="ed-section container">
  <p class="ed-label">PIPELINE</p>
  <div class="pipeline">{' <span>→</span> '.join(e(step) for step in site["pipeline"])}</div>
  <p>GitHub Actions ingest public RSS into <code>data/ingest/rss-inbox.json</code>. Every ingested record has editorial_state=INBOX and publish=false. Nothing in that file is rendered as a briefing or a signal.</p>
</section>
<section class="ed-section container">
  <p class="ed-label">OBJECTS</p>
  <p>SIGNAL · BRIEFING · TOPIC · ENTITY · SOURCE · COLLECTION. Records live in <code>data/network.json</code>. Pages are generated statically so the important content is crawlable HTML.</p>
</section>
<section class="ed-section container">
  <p class="ed-label">CONNECT</p>
  <p><a href="{e(site["author"]["github"])}">GitHub</a> · <a href="{e(site["author"]["x"])}">X</a> · <a href="/lab/">Lab</a></p>
</section>
"""
    return layout(
        data,
        title="About — The Tech Briefing",
        description="What The Tech Briefing is, how records are sourced, and why RSS is not the product.",
        route="/about/",
        active="about",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(site, crumb)],
    )


def lab_index(data: dict) -> str:
    lab = data["lab"]
    crumb = [("/", "Home"), ("/lab/", "Lab")]
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">LAB LAYER // SECONDARY</p>
  <h1>THE<br><span>LAB.</span></h1>
  <p>{e(lab["tagline"])}</p>
  <div class="lab-nav">
    <a href="/lab/projects/">PROJECTS</a>
    <a href="/lab/systems/">SYSTEMS</a>
    <a href="/lab/reference/">REFERENCE</a>
    <a href="/lab/experiments/">EXPERIMENTS</a>
    <a href="/lab/experiments/xeno-signal/">XENO SIGNAL</a>
  </div>
</section>
<section class="ed-section container">
  <p class="ed-label">ABOUT THE BUILDER</p>
  <h2>{e(lab["about"]["headline"])}</h2>
  {"".join(f"<p>{e(p)}</p>" for p in lab["about"]["paragraphs"])}
</section>
<section class="ed-section container">
  <p class="ed-label">ACTIVE / COMPLETE</p>
  <div class="row-list">{"".join(row(f"<b>{e(p['code'])}</b><br>{e(p['status'])}", p["title"], "/lab/projects/", p["summary"]) for p in lab["projects"][:2])}</div>
</section>
<section class="ed-section container">
  <p class="ed-label">CAPABILITY MATRIX</p>
  <div class="row-list">{"".join(row(f"<b>{e(c['code'])}</b>", c["title"], "/lab/systems/", c["text"]) for c in lab["capabilities"])}</div>
</section>
"""
    return layout(
        data,
        title="Lab — The Tech Briefing",
        description="Portfolio, systems, reference, and experiments. Secondary to the briefing network.",
        route="/lab/",
        active="lab",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def lab_projects(data: dict) -> str:
    crumb = [("/", "Home"), ("/lab/", "Lab"), ("/lab/projects/", "Projects")]
    featured = [p for p in data["lab"]["projects"] if p.get("detail")]
    queued = [p for p in data["lab"]["projects"] if not p.get("detail")]
    feat_html = []
    for project in featured:
        flow = ""
        if project.get("flow"):
            flow = "<div class=\"lab-flow\">" + "<i>→</i>".join(f"<span>{e(step)}</span>" for step in project["flow"]) + "</div>"
        tags = "".join(f"<span>{e(tag)}</span>" for tag in project.get("tags", []))
        feat_html.append(f"""<article class="project featured">
          <div class="project-index">{e(project["code"])}</div>
          <div class="project-main">
            <p class="project-tag">{e(project["status"])}</p>
            <h2>{e(project["title"])}</h2>
            <p>{e(project["detail"])}</p>
            {flow}
            <div class="tags">{tags}</div>
          </div>
          <a class="project-link" href="{e(project["url"])}" rel="noopener noreferrer">OPEN REPOSITORY ↗</a>
        </article>""")
    queued_html = "".join(
        f"""<article class="project placeholder"><div class="mini-icon">{e(p["code"])}</div>
        <p class="project-tag">{e(p["status"])}</p><h3>{e(p["title"])}</h3><p>{e(p["summary"])}</p>
        <a class="project-link" href="{e(p["url"])}" rel="noopener noreferrer">REPOSITORY ↗</a></article>"""
        for p in queued
    )
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">LAB / PROJECTS</p>
  <h1>PROJECTS<span>.</span></h1>
  <p>Real systems work. Queued items are labeled as queued.</p>
  <div class="lab-nav"><a href="/lab/">LAB HOME</a><a href="/lab/systems/">SYSTEMS</a><a href="/lab/reference/">REFERENCE</a></div>
</section>
<section class="section container"><div class="section-label">FEATURED</div><div class="section-content">{"".join(feat_html)}</div></section>
<section class="section container"><div class="section-label">QUEUE</div><div class="section-content"><div class="project-grid">{queued_html}</div></div></section>
"""
    return layout(
        data,
        title="Lab projects — The Tech Briefing",
        description="Windows infrastructure, networking, and queued systems projects.",
        route="/lab/projects/",
        active="lab",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def lab_systems(data: dict) -> str:
    crumb = [("/", "Home"), ("/lab/", "Lab"), ("/lab/systems/", "Systems")]
    cards = []
    for system in data["lab"]["systems"]:
        specs = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in system["specs"].items())
        tags = "".join(f"<span>{e(tag)}</span>" for tag in system["tags"])
        cards.append(f"""<article class="device"><div class="device-top"><span>{e(system["code"])}</span><b>{e(system["status"])}</b></div>
        <h2>{e(system["title"])}</h2><p class="role">{e(system["role"])}</p><dl>{specs}</dl>
        <div class="device-tags">{tags}</div></article>""")
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">LAB / HARDWARE</p>
  <h1>MY<br><span>SYSTEMS.</span></h1>
  <p>The machines used to build, test, learn and experiment.</p>
</section>
<section class="section container"><div class="section-label">ACTIVE SYSTEMS</div>
<div class="section-content"><div class="device-grid">{"".join(cards)}</div></div></section>
"""
    return layout(
        data,
        title="Lab systems — The Tech Briefing",
        description="Hardware and operating systems inventory.",
        route="/lab/systems/",
        active="lab",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def lab_reference(data: dict) -> str:
    crumb = [("/", "Home"), ("/lab/", "Lab"), ("/lab/reference/", "Reference")]
    cards = "".join(
        f'<a class="reference-card" href="{e(item["url"])}" rel="noopener noreferrer"><b>{e(item["code"])} // {e(item["title"].upper())}</b><span>{e(item["summary"])}</span></a>'
        for item in data["lab"]["reference"]
    )
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">LAB / KNOWLEDGE BASE</p>
  <h1>TECHNICAL<br><span>REFERENCE.</span></h1>
  <p>Commands, concepts and troubleshooting notes collected while building real systems.</p>
</section>
<section class="section container"><div class="section-label">REFERENCE INDEX</div>
<div class="section-content"><div class="reference-grid">{cards}</div></div></section>
"""
    return layout(
        data,
        title="Lab reference — The Tech Briefing",
        description="Technical command and troubleshooting library.",
        route="/lab/reference/",
        active="lab",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def lab_experiments(data: dict) -> str:
    crumb = [("/", "Home"), ("/lab/", "Lab"), ("/lab/experiments/", "Experiments")]
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">LAB / EXPERIMENTS</p>
  <h1>EXPERIMENTS<span>.</span></h1>
  <p>Interactive and unfinished work that does not belong in a briefing.</p>
</section>
<section class="ed-section container">
  <div class="row-list">
    {row("<b>XENO</b><br>ACTIVE", "Xeno Signal", "/lab/experiments/xeno-signal/", "Interactive deep-space flight computer. Isolated experiment, preserved from the original site.")}
  </div>
</section>
"""
    return layout(
        data,
        title="Lab experiments — The Tech Briefing",
        description="Lab experiments including Xeno Signal.",
        route="/lab/experiments/",
        active="lab",
        body=body,
        crumbs=crumb,
        ld=[crumb_ld(data["site"], crumb)],
    )


def xeno_page(data: dict) -> str:
    crumb = [
        ("/", "Home"),
        ("/lab/", "Lab"),
        ("/lab/experiments/", "Experiments"),
        ("/lab/experiments/xeno-signal/", "Xeno Signal"),
    ]
    markup = XENO_MAIN.read_text(encoding="utf-8")
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">LAB EXPERIMENT // PRESERVED</p>
  <p>Xeno Signal remains an isolated experiment. It is not part of the briefing network.</p>
</section>
<main class="signal-page container">{markup}</main>
"""
    # nested <main> is invalid; use a div wrapper instead of extra main — the layout already has main
    body = f"""
<section class="container" style="padding-top:28px">{breadcrumbs(crumb)}</section>
<div class="signal-page container">{markup}</div>
"""
    return layout(
        data,
        title="Xeno Signal — Lab experiment",
        description="Xeno Signal interactive deep-space interface. A Lab experiment, not a briefing.",
        route="/lab/experiments/xeno-signal/",
        active="lab",
        body=body,
        crumbs=crumb,
        extra_css=["/css/xeno-signal.css"],
        extra_js=["/js/xeno-signal.js"],
        ld=[crumb_ld(data["site"], crumb)],
    )


def redirect_page(target: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={e(target)}">
<link rel="canonical" href="https://thetechbriefing.com{e(target)}">
<title>{e(title)}</title>
<script>location.replace({json.dumps(target)});</script>
</head>
<body>
<p>This page moved to <a href="{e(target)}">{e(target)}</a>.</p>
</body>
</html>
"""


def not_found(data: dict) -> str:
    crumb = [("/", "Home")]
    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">404</p>
  <h1>NO RECORD<span>.</span></h1>
  <p>That path is not in the published network. Try search, briefings, or the lab.</p>
  <div class="lab-nav"><a href="/">HOME</a><a href="/search/">SEARCH</a><a href="/lab/">LAB</a></div>
</section>
"""
    html_out = layout(
        data,
        title="Not found — The Tech Briefing",
        description="No published record at this path.",
        route="/404.html",
        active="home",
        body=body,
        crumbs=crumb,
    )
    return html_out.replace('<meta name="robots" content="index,follow">', '<meta name="robots" content="noindex">')


def search_index(data: dict) -> list[dict]:
    items = []

    def add(record_id, type_, title, summary, body, url, topics=None, entities=None, sources=None, date=None):
        items.append(
            {
                "id": record_id,
                "type": type_,
                "title": title,
                "summary": summary or "",
                "body": body or "",
                "url": url,
                "topics": topics or [],
                "entities": entities or [],
                "sources": [s["id"] if isinstance(s, dict) else s for s in (sources or [])],
                "date": date or "",
            }
        )

    for briefing in data["briefings"]:
        add(
            briefing["id"],
            "briefing",
            briefing["title"],
            briefing["deck"],
            " ".join(briefing.get("takeaways", []) + briefing.get("what_happened", []) + briefing.get("why_it_matters", [])),
            f"/briefings/{briefing['slug']}/",
            briefing.get("topics"),
            briefing.get("entities"),
            briefing.get("sources"),
            briefing.get("published"),
        )
    for signal in data["signals"]:
        add(
            signal["id"],
            "signal",
            signal["title"],
            signal["summary"],
            signal.get("body", ""),
            f"/signals/{signal['slug']}/",
            signal.get("topics"),
            signal.get("entities"),
            signal.get("sources"),
            signal.get("published"),
        )
    for topic in data["topics"]:
        add(topic["id"], "topic", topic["name"], topic["summary"], topic.get("current_status", ""), f"/topics/{topic['slug']}/", [topic["id"]])
    for entity in data["entities"]:
        add(entity["id"], "entity", entity["name"], entity["summary"], entity.get("notes", ""), f"/entities/{entity['slug']}/", [], [entity["id"]])
    for collection in data["collections"]:
        add(collection["id"], "collection", collection["name"], collection["summary"], collection.get("notes", ""), f"/collections/{collection['slug']}/", collection.get("topics"), collection.get("entities"))
    for project in data["lab"]["projects"]:
        add(project["id"], "lab", project["title"], project["summary"], project.get("detail", ""), "/lab/projects/", [], [], [], "")
    add("xeno-signal", "lab", "Xeno Signal", "Interactive deep-space experiment.", "lab experiment flight computer", "/lab/experiments/xeno-signal/")
    return items


def sitemap(data: dict, routes: list[str]) -> str:
    urls = []
    today = data["site"]["edition"]["date"]
    for route in routes:
        loc = data["site"]["url"] + (route if route != "/" else "/")
        urls.append(f"  <url><loc>{e(loc)}</loc><lastmod>{e(today)}</lastmod></url>")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"


def robots(data: dict) -> str:
    return f"""User-agent: *
Allow: /
Disallow: /data/ingest/

Sitemap: {data["site"]["url"]}/sitemap.xml
"""


def atom_feed(data: dict) -> str:
    site = data["site"]
    entries = []
    for briefing in data["briefings"]:
        url = site["url"] + f"/briefings/{briefing['slug']}/"
        entries.append((briefing["published"], briefing["id"], briefing["title"], briefing["deck"], url, "briefing"))
    for signal in data["signals"]:
        url = site["url"] + f"/signals/{signal['slug']}/"
        entries.append((signal["published"], signal["id"], signal["title"], signal["deck"], url, "signal"))
    entries.sort(key=lambda x: x[0], reverse=True)
    xml_entries = []
    for published, record_id, title, deck, url, kind in entries:
        xml_entries.append(
            f"""  <entry>
    <id>tag:thetechbriefing.com,{e(published)}:{e(record_id)}</id>
    <title>{e(title)}</title>
    <link href="{e(url)}" rel="alternate"/>
    <published>{e(published)}T00:00:00Z</published>
    <updated>{e(published)}T00:00:00Z</updated>
    <category term="{e(kind)}"/>
    <summary>{e(deck)}</summary>
  </entry>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{e(site["name"])}</title>
  <subtitle>{e(site["tagline"])}</subtitle>
  <link href="{e(site["url"])}/feed.xml" rel="self"/>
  <link href="{e(site["url"])}/"/>
  <updated>{e(site["edition"]["date"])}T00:00:00Z</updated>
  <id>{e(site["url"])}/</id>
  <author><name>{e(site["author"]["name"])}</name></author>
{chr(10).join(xml_entries)}
</feed>
"""


def intelligence_page(data: dict) -> str:
    site = data["site"]
    crumb = [("/", "Home"), ("/intelligence/", "Intelligence")]
    store = IntelligenceStore()
    events = store.latest_events(limit=50)
    all_articles = store.articles()
    articles = all_articles[:30]
    assets_list = store.assets()
    markets_list = store.markets()
    price_obs = store.price_observations()
    reactions = store.historical_reactions()
    prediction_obs = store.prediction_market_observations()
    probabilities = store.probability_observations()
    country_events = country_event_summary(store.latest_events(limit=10_000))

    sector_counts: dict[str, int] = {}
    for article in all_articles:
        ps = article.get("primary_sector")
        if ps:
            sector_counts[ps] = sector_counts.get(ps, 0) + 1

    event_rows = []
    for ev in events:
        facts = ev.get("facts") or []
        fact_block = "".join(f"<li>{e(f)}</li>" for f in facts)
        interp_block = ""
        if ev.get("interpretations"):
            interp_block = "<dt>INTERPRETATION</dt><dd>" + "<br>".join(e(i) for i in ev["interpretations"]) + "</dd>"
        prov = ev.get("provenance") or {}
        geo = ev.get("geography") or {}
        geo_bits = []
        if geo.get("event_country_ids"):
            geo_bits.append("event: " + ", ".join(geo["event_country_ids"]))
        if geo.get("headquarters_country_ids"):
            geo_bits.append("hq: " + ", ".join(geo["headquarters_country_ids"]))
        if geo.get("regulatory_country_ids"):
            geo_bits.append("regulatory: " + ", ".join(geo["regulatory_country_ids"]))
        geo_block = f'<div><dt>GEOGRAPHY</dt><dd>{e(" · ".join(geo_bits) or "—")}</dd></div>' if geo_bits or ev.get("countries") else ""
        sectors_block = ""
        if ev.get("sectors"):
            sectors_block = f'<div><dt>SECTORS</dt><dd>{e(", ".join(ev["sectors"]))}</dd></div>'
        assets_block = ""
        if ev.get("assets"):
            assets_block = f'<div><dt>ASSETS</dt><dd>{e(", ".join(ev["assets"]))}</dd></div>'
        event_rows.append(
            f"""<article class="intel-event">
  <header><span class="intel-type">{e(ev.get("event_type", "").replace("_", " ").upper())}</span>
  <time datetime="{e(ev.get("timestamp", ""))}">{e(ev.get("timestamp", "—")[:19])}</time></header>
  <ul class="intel-facts">{fact_block}</ul>
  <dl class="intel-meta">
    <div><dt>SOURCE</dt><dd><a href="{e(prov.get("canonical_url", "#"))}" rel="noopener noreferrer">{e(prov.get("source_name", ""))}</a></dd></div>
    <div><dt>CONFIDENCE</dt><dd>{e(ev.get("confidence", ""))}</dd></div>
    <div><dt>STATUS</dt><dd>{e(ev.get("interpretation_status", ""))}</dd></div>
    <div><dt>ENTITIES</dt><dd>{e(", ".join(ev.get("entities", [])) or "—")}</dd></div>
    {geo_block}
    {sectors_block}
    {assets_block}
    {interp_block}
  </dl>
</article>"""
        )

    asset_rows = "".join(
        f'<li><b>{e(a["symbol"])}</b> — {e(a["name"])} <span class="intel-tag">{e(a["asset_class"])}</span></li>'
        for a in assets_list
    )
    market_rows = "".join(
        f'<li><b>{e(m["symbol"])}</b> @ {e(m["venue"])} <span class="intel-tag">{e(m["market_type"])}</span></li>'
        for m in markets_list
    )
    sector_rows = "".join(
        f'<li><b>{e(SECTOR_LABELS.get(sid, sid))}</b> <span class="intel-tag">{count}</span></li>'
        for sid, count in sorted(sector_counts.items(), key=lambda x: (-x[1], x[0]))
    )
    price_rows = "".join(
        f'<li><b>{e(o.get("symbol", o.get("asset_id", "")))}</b> {e(str(o.get("price", "—")))} '
        f'<span class="intel-tag">{e(o.get("source", ""))}</span></li>'
        for o in price_obs[:10]
    )
    country_rows = "".join(
        f'<li><b>{e(cid)}</b> <span class="intel-tag">{meta.get("event_count", 0)} events</span></li>'
        for cid, meta in sorted(country_events.items(), key=lambda x: -x[1].get("event_count", 0))[:12]
    )

    body = f"""
<section class="page-head container">
  {breadcrumbs(crumb)}
  <p class="masthead-kicker">MARKET INTELLIGENCE FOUNDATION</p>
  <h1>INTELLIGENCE<span>.</span></h1>
  <p class="console-sub">Structured events and market observations derived from ingested sources. Editorial inbox items are never auto-published. No trading signals. No fabricated probabilities.</p>
</section>
<section class="console container">
  <div class="panel">
    <div class="panel-head"><span class="panel-title">PIPELINE</span><span class="panel-note">STAGE 4 · $0/MO</span></div>
    <p class="panel-foot" style="border-top:0">{" → ".join(e(step) for step in ["SOURCE", "ARTICLE", "EVENT", "ENTITY", "COUNTRY", "SECTOR", "ASSET", "MARKET", "OBSERVATION", "HISTORICAL REACTION", "PROBABILITY"])}</p>
  </div>
  <div class="console-grid">
    <div class="panel">
      <div class="panel-head"><span class="panel-title">COVERAGE</span><span class="panel-note">{len(all_articles)} ARTICLES · {len(events)} EVENTS</span></div>
      <ul class="intel-list">{sector_rows or "<li>No sector coverage yet.</li>"}</ul>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">GEOGRAPHY</span><span class="panel-note">{len(country_events)} COUNTRIES</span></div>
      <ul class="intel-list">{country_rows or "<li>No country associations yet.</li>"}</ul>
    </div>
  </div>
  <div class="console-grid">
    <div class="panel">
      <div class="panel-head"><span class="panel-title">ASSETS</span><span class="panel-note">{len(assets_list)} REGISTERED</span></div>
      <ul class="intel-list">{asset_rows or "<li>No assets registered yet.</li>"}</ul>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">MARKETS</span><span class="panel-note">{len(markets_list)} REGISTERED</span></div>
      <ul class="intel-list">{market_rows or "<li>No markets registered yet.</li>"}</ul>
    </div>
  </div>
  <div class="console-grid">
    <div class="panel">
      <div class="panel-head"><span class="panel-title">PRICE OBSERVATIONS</span><span class="panel-note">{len(price_obs)} LIVE</span></div>
      <ul class="intel-list">{price_rows or "<li>No price observations yet.</li>"}</ul>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">RESEARCH DATA</span><span class="panel-note">{len(reactions)} REACTIONS</span></div>
      <ul class="intel-list">
        <li><b>Historical reactions</b> <span class="intel-tag">{len(reactions)}</span></li>
        <li><b>Prediction markets</b> <span class="intel-tag">{len(prediction_obs)}</span></li>
        <li><b>Market-implied probabilities</b> <span class="intel-tag">{len(probabilities)}</span></li>
      </ul>
      <p class="panel-foot">Observations only. NULL where data is unavailable. No buy/sell labels.</p>
    </div>
  </div>
  <div class="panel">
    <div class="panel-head"><span class="panel-title">STRUCTURED EVENTS</span><span class="panel-note">{len(events)} EXTRACTED</span></div>
    <div class="intel-events">{"".join(event_rows) if event_rows else empty("No events extracted yet. Run scripts/run_ingest.py.")}</div>
    <p class="panel-foot">Facts are listed verbatim from source titles/summaries. Geography uses explicit evidence only.</p>
  </div>
  <div class="panel">
    <div class="panel-head"><span class="panel-title">INGESTED ARTICLES</span><span class="panel-note">{len(all_articles)} IN INBOX</span></div>
    <ul class="intel-list">
      {"".join(f'<li><a href="{e(a["canonical_url"])}" rel="noopener noreferrer">{e(a["title"])}</a> <span class="intel-tag">{e(a.get("primary_sector") or a["source_id"])}</span></li>' for a in articles[:20])}
    </ul>
  </div>
</section>
"""
    return layout(
        data,
        title=f"Intelligence — {site['name']}",
        description="Structured market intelligence foundation: ingested events, assets, and markets.",
        route="/intelligence/",
        active="intelligence",
        body=body,
        crumbs=crumb,
        extra_css=["/css/dashboard.css"],
        ld=[crumb_ld(site, crumb)],
    )


def main() -> None:
    """Do not publish the retired network console over the portfolio.

    index.html is the hand-written X pin. Running the old generator would
    replace that page, the about/archive routes, sitemap, and robots file.
    The previous console is kept as a snapshot under archive/network-console/.
    Tech Briefing itself is https://thetechbriefing.com.
    """
    raise SystemExit(
        "build_site.py no longer publishes to the site root.\n"
        "The public site is the static portfolio in index.html.\n"
        "Tech Briefing lives at https://thetechbriefing.com.\n"
        "The previous console snapshot is under archive/network-console/."
    )

    import subprocess
    import sys

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_voxel_world.py")], check=True)

    try:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "run_ingest.py")], check=True)
    except subprocess.CalledProcessError:
        print("WARN: ingestion pipeline failed; continuing build with existing intelligence data")

    write_intelligence_public(ROOT)

    manifest = assets.publish_assets(ROOT)
    assets.configure(manifest)

    data = load()
    routes: list[str] = []

    pages = {
        "/": homepage(data),
        "/briefings/": briefings_index(data),
        "/signals/": signals_index(data),
        "/intelligence/": intelligence_page(data),
        "/topics/": topics_index(data),
        "/entities/": entities_index(data),
        "/archive/": archive_page(data),
        "/about/": about_page(data),
        "/lab/": lab_index(data),
        "/lab/projects/": lab_projects(data),
        "/lab/systems/": lab_systems(data),
        "/lab/reference/": lab_reference(data),
        "/lab/experiments/": lab_experiments(data),
        "/lab/experiments/xeno-signal/": xeno_page(data),
    }
    for briefing in data["briefings"]:
        pages[f"/briefings/{briefing['slug']}/"] = briefing_page(data, briefing)
    for signal in data["signals"]:
        pages[f"/signals/{signal['slug']}/"] = signal_page(data, signal)
    for topic in data["topics"]:
        pages[f"/topics/{topic['slug']}/"] = topic_page(data, topic)
    for entity in data["entities"]:
        pages[f"/entities/{entity['slug']}/"] = entity_page(data, entity)
    for collection in data["collections"]:
        pages[f"/collections/{collection['slug']}/"] = collection_page(data, collection)

    index_items = search_index(data)
    pages["/search/"] = search_page(data, index_items)

    for route, html_out in pages.items():
        write(page_file(route), html_out)
        routes.append(route)

    write(ROOT / "404.html", not_found(data))
    write_if_changed(
        ROOT / "data" / "search-index.json",
        {"generated_at": datetime.now(timezone.utc).isoformat(), "items": index_items},
    )
    write_if_changed(
        ROOT / "data" / "dashboard.json",
        dashboard_data(data),
    )
    write(ROOT / "sitemap.xml", sitemap(data, routes))
    write(ROOT / "robots.txt", robots(data))
    write(ROOT / "feed.xml", atom_feed(data))
    write(ROOT / ".nojekyll", "")

    redirects = {
        "tech.html": "/signals/",
        "lab.html": "/lab/",
        "systems.html": "/lab/systems/",
        "reference.html": "/lab/reference/",
        "signal.html": "/lab/experiments/xeno-signal/",
    }
    for filename, target in redirects.items():
        write(ROOT / filename, redirect_page(target, f"Redirecting to {target}"))

    print(
        f"Wrote {len(pages)} pages, search index ({len(index_items)} items), "
        f"{len(manifest)} hashed assets, sitemap, feed, redirects."
    )


if __name__ == "__main__":
    main()
