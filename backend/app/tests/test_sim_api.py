"""API tests for the sim/inspector router (deterministic hand-driven runtime)."""


async def test_status_shape(sim_client):
    ac, rt = sim_client
    r = await ac.get("/sim/status")
    assert r.status_code == 200
    body = r.json()
    assert set(["running", "active", "viewers", "speed", "sim_clock", "market_density", "lines"]) <= body.keys()
    assert len(body["lines"]) == 4
    line = body["lines"][0]
    assert {"ad_id", "brand", "objective", "daily_budget", "spent_today"} <= line.keys()


async def test_status_503_without_runtime(client):
    r = await client.get("/sim/status")
    assert r.status_code == 503


async def test_control_patch_updates_density(sim_client):
    ac, rt = sim_client
    r = await ac.post("/sim/control", json={"market_density": 1.8})
    assert r.status_code == 200
    assert r.json()["market_density"] == 1.8
    # Reflected in a subsequent status read.
    assert (await ac.get("/sim/status")).json()["market_density"] == 1.8
    assert rt.world.economy.market_density == 1.8


async def test_control_rejects_bad_speed(sim_client):
    ac, _ = sim_client
    r = await ac.post("/sim/control", json={"speed": -5})
    assert r.status_code == 422  # pydantic gt=0


async def test_delivery_series(sim_client):
    ac, _ = sim_client
    r = await ac.get("/sim/delivery?window=200")
    assert r.status_code == 200
    points = r.json()["points"]
    assert points
    p = points[0]
    assert {"t", "impressions", "clicks", "conversions", "spend", "revenue"} <= p.keys()


async def test_rtb_samples_list_and_detail(sim_client):
    ac, _ = sim_client
    r = await ac.get("/sim/rtb/samples")
    assert r.status_code == 200
    samples = r.json()["samples"]
    assert samples
    sid = samples[0]["id"]
    d = await ac.get(f"/sim/rtb/samples/{sid}")
    assert d.status_code == 200
    detail = d.json()
    assert "request" in detail and "bids" in detail and "notices" in detail
    assert detail["request"]["at"] in (1, 2)


async def test_rtb_sample_404(sim_client):
    ac, _ = sim_client
    assert (await ac.get("/sim/rtb/samples/999999")).status_code == 404


async def test_rtb_replay(sim_client):
    ac, _ = sim_client
    r = await ac.post("/sim/rtb/replay", json={})
    assert r.status_code == 200
    detail = r.json()
    assert "request" in detail and "bids" in detail
    # eligible bids carry seat + price
    for b in detail["bids"]["eligible"]:
        assert "seat" in b and "price" in b
