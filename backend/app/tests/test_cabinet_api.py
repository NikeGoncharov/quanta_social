"""Cabinet API: accounts, targeting, wizard estimate, campaign CRUD + grid, reporting,
diagnostics. The runtime and request-path DB share one temp database (cabinet_client)."""


async def test_default_account_created(cabinet_client):
    ac, _ = cabinet_client
    r = await ac.get("/cabinet/account")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "acct-local" and body["currency"] == "USD"


async def test_targeting_options_and_audience(cabinet_client):
    ac, _ = cabinet_client
    opts = (await ac.get("/cabinet/targeting/options")).json()
    assert "tech" in opts["interests"] and "USA" in opts["geos"]
    assert opts["age_bands"] and opts["genders"]

    r = await ac.post("/cabinet/targeting/audience", json={"targeting": {"interests": ["finance"], "geos": ["USA"]}})
    aud = r.json()
    assert aud["audience"] > 0 and aud["segments"] > 0
    assert 0 < aud["reach_pct"] < 1

    # Narrower targeting -> strictly smaller audience.
    broad = (await ac.post("/cabinet/targeting/audience", json={"targeting": {"interests": ["finance"]}})).json()
    assert broad["audience"] > aud["audience"]


async def test_wizard_estimate(cabinet_client):
    ac, _ = cabinet_client
    r = await ac.post(
        "/cabinet/wizard/estimate",
        json={"objective": "traffic", "daily_budget_usd": 200, "bid_usd": 1.0,
              "targeting": {"interests": ["gaming"]}},
    )
    assert r.status_code == 200
    est = r.json()
    assert est["conversions"] <= est["clicks"] <= est["impressions"] <= est["auctions"]
    assert est["result_label"] == "clicks" and est["results"] == est["clicks"]
    assert est["audience"] > 0


async def test_grid_lists_seeds_with_live_metrics(cabinet_client):
    from app.sim.seed import seed_lines

    ac, _ = cabinet_client
    rows = (await ac.get("/cabinet/grid")).json()["rows"]
    assert len(rows) == len(seed_lines())  # the seed roster
    by_id = {r["campaign_id"]: r for r in rows}
    volt = by_id["seed-voltmatic-cmp"]
    assert volt["status"] == "active" and volt["objective"] == "traffic"
    assert volt["live"] is not None  # active -> live delivery block present
    assert volt["live"]["impressions_today"] >= 0


async def test_campaign_crud_and_live_delivery(cabinet_client):
    ac, rt = cabinet_client
    # Publish a new campaign.
    create = await ac.post(
        "/cabinet/campaigns",
        json={
            "name": "Cabinet-made", "objective": "awareness", "daily_budget_usd": 300,
            "bid_usd": 8.0, "targeting": {"interests": ["tech", "gaming"]},
            "creative": {"title": "Hello", "brand_name": "Cabinetco", "link_url": "https://cabinetco.example"},
        },
    )
    assert create.status_code == 201
    cid = create.json()["campaign_id"]
    assert create.json()["daily_budget_usd"] == 300.0

    # It joined the live roster (the POST requested a reload; hand-driven runtime reloads here).
    await rt.reload_lines()
    assert any(ln.campaign_id == cid for ln in rt.lines)
    for _ in range(20):
        rt.step_once()
    await rt.flush(final=True)
    delivered = next(ln for ln in rt.lines if ln.campaign_id == cid)
    assert rt.state.spent_today_micros.get(delivered.ad_id, 0) > 0  # it delivered

    # Edit: raise budget via PATCH.
    patch = await ac.patch(f"/cabinet/campaigns/{cid}", json={"daily_budget_usd": 500})
    assert patch.status_code == 200 and patch.json()["daily_budget_usd"] == 500.0

    # Pause it -> drops from the live grid's active set on reload.
    await ac.patch(f"/cabinet/campaigns/{cid}", json={"status": "paused"})
    await rt.reload_lines()
    assert not any(ln.campaign_id == cid for ln in rt.lines)

    # Delete it.
    dele = await ac.delete(f"/cabinet/campaigns/{cid}")
    assert dele.status_code == 204
    assert (await ac.get(f"/cabinet/campaigns/{cid}")).status_code == 404


async def test_campaign_404(cabinet_client):
    ac, _ = cabinet_client
    assert (await ac.get("/cabinet/campaigns/nope")).status_code == 404
    assert (await ac.patch("/cabinet/campaigns/nope", json={"name": "x"})).status_code == 404
    assert (await ac.delete("/cabinet/campaigns/nope")).status_code == 404


async def test_reporting_kpis_match_delivery(cabinet_client):
    ac, _ = cabinet_client
    r = await ac.get("/cabinet/reporting/kpis?window=1440")
    assert r.status_code == 200
    body = r.json()
    cur = body["current"]
    assert cur["impressions"] > 0
    assert cur["clicks"] <= cur["impressions"]
    assert "deltas" in body

    # Per-campaign KPIs are a subset of the global totals.
    volt = await ac.get("/cabinet/reporting/kpis?campaign_id=seed-voltmatic-cmp&window=1440")
    assert volt.json()["current"]["impressions"] <= cur["impressions"]


async def test_reporting_timeseries_and_breakdown(cabinet_client):
    ac, _ = cabinet_client
    ts = (await ac.get("/cabinet/reporting/timeseries?bin=30&window=48")).json()
    assert ts["bin"] == 30
    for p in ts["points"]:
        assert p["t"] % 30 == 0

    bd = (await ac.get("/cabinet/reporting/breakdown?dimension=interest")).json()
    assert bd["dimension"] == "interest" and bd["rows"]
    # Ranked by impressions, descending.
    imps = [row["impressions"] for row in bd["rows"]]
    assert imps == sorted(imps, reverse=True)

    assert (await ac.get("/cabinet/reporting/breakdown?dimension=bogus")).status_code == 400


async def test_patch_null_is_ignored_not_500(cabinet_client):
    """An explicit JSON null for a non-nullable field is treated as 'no change', never a 500."""
    ac, _ = cabinet_client
    r = await ac.patch("/cabinet/campaigns/seed-nimbus-cmp", json={"daily_budget_usd": None, "name": None})
    assert r.status_code == 200
    assert r.json()["daily_budget_usd"] == 500.0  # unchanged
    assert r.json()["name"] == "Nimbus X launch"


async def test_engagement_bid_landscape_uses_human_label(cabinet_client):
    """The Engagement objective counts clicks but must be LABELLED 'engagements' everywhere,
    including the bid landscape (not the raw result key 'clicks')."""
    ac, rt = cabinet_client
    create = await ac.post(
        "/cabinet/campaigns",
        json={
            "name": "Eng test", "objective": "engagement", "daily_budget_usd": 100, "bid_usd": 0.5,
            "targeting": {"interests": ["music"]},
            "creative": {"title": "Vibe", "brand_name": "Engco", "link_url": "https://engco.example"},
        },
    )
    cid = create.json()["campaign_id"]
    await rt.reload_lines()
    land = (await ac.get(f"/cabinet/campaigns/{cid}/bid-landscape")).json()
    assert land["result_label"] == "engagements"


async def test_diagnostics_why_and_bid_landscape(cabinet_client):
    ac, _ = cabinet_client
    why = (await ac.get("/cabinet/campaigns/seed-meridian-cmp/why")).json()
    assert why["limiter"] in ("audience", "budget", "frequency", "bid", "learning", None)
    assert "headline" in why and "detail" in why

    land = (await ac.get("/cabinet/campaigns/seed-nimbus-cmp/bid-landscape")).json()
    pts = land["points"]
    assert any(p["is_current"] for p in pts)
    # Win rate is monotonically non-decreasing in the bid.
    wrs = [p["win_rate"] for p in pts]
    assert wrs == sorted(wrs)

    # A non-existent / not-on-air campaign has no live landscape.
    assert (await ac.get("/cabinet/campaigns/nope/bid-landscape")).status_code == 404
