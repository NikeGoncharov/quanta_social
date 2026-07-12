// Objective-first campaign wizard on one page: pick a goal, set bid + budget, target, write
// the creative — with a live delivery estimate and a sponsored-card preview pinned alongside,
// so every choice's effect is visible before publishing (the glass-box, at authoring time).
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  cabinetApi,
  type Creative,
  type EstimateResult,
  type Objective,
  type TargetingOptions,
  type TargetingSpec,
} from "../api/cabinet";
import { CreativePreview } from "./CreativePreview";
import { compact, usd } from "./format";
import { STOCK } from "./stock";
import { TargetingEditor } from "./TargetingEditor";

const OBJECTIVES: { key: Objective; name: string; stage: string; desc: string }[] = [
  { key: "awareness", name: "Awareness", stage: "TOF", desc: "Maximize reach. Billed on impressions (CPM)." },
  { key: "traffic", name: "Traffic", stage: "MOF", desc: "Drive link clicks. Billed on clicks (CPC)." },
  { key: "engagement", name: "Engagement", stage: "MOF", desc: "Earn post reactions and interactions." },
  { key: "conversions", name: "Conversions", stage: "BOF", desc: "Optimize for conversions. Has a learning phase." },
];

const DEFAULT_BID: Record<Objective, number> = { awareness: 6, traffic: 0.85, engagement: 0.5, conversions: 40 };
const BID_HINT: Record<Objective, string> = {
  awareness: "CPM bid — $ per 1,000 impressions",
  traffic: "CPC bid — $ per link click",
  engagement: "Cost per engagement",
  conversions: "Target CPA — $ per conversion",
};

const EMPTY_TARGETING: TargetingSpec = { interests: [], geos: [], age_bands: [], genders: [] };

export default function CreateWizard() {
  const nav = useNavigate();
  const [options, setOptions] = useState<TargetingOptions | null>(null);

  const [objective, setObjective] = useState<Objective>("traffic");
  const [name, setName] = useState("");
  const [bid, setBid] = useState(DEFAULT_BID.traffic);
  const [budget, setBudget] = useState(200);
  const [value, setValue] = useState(60);
  const [pacing, setPacing] = useState<"even" | "asap">("even");
  const [targeting, setTargeting] = useState<TargetingSpec>(EMPTY_TARGETING);
  const [creative, setCreative] = useState<Creative>({
    title: "",
    body: "",
    cta_text: "Learn more",
    brand_name: "",
    main_image_key: STOCK[0].key,
    link_url: "",
  });

  const [est, setEst] = useState<EstimateResult | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    cabinetApi.targetingOptions().then(setOptions).catch(() => {});
  }, []);

  // Changing the objective resets the bid to a sensible default for its billing model.
  const pickObjective = (o: Objective) => {
    setObjective(o);
    setBid(DEFAULT_BID[o]);
  };

  const estKey = JSON.stringify({ objective, bid, budget, value, targeting });
  useEffect(() => {
    let alive = true;
    const id = setTimeout(() => {
      cabinetApi
        .estimate({ objective, daily_budget_usd: budget, bid_usd: bid, value_usd: value, targeting })
        .then((r) => alive && setEst(r))
        .catch(() => {});
    }, 300);
    return () => {
      alive = false;
      clearTimeout(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estKey]);

  const valid = name.trim().length > 0 && creative.title.trim().length > 0 && bid > 0 && budget > 0;

  const publish = async (status: "active" | "draft") => {
    if (!valid) return;
    setPublishing(true);
    setError(null);
    try {
      const created = await cabinetApi.create({
        name: name.trim(),
        objective,
        daily_budget_usd: budget,
        bid_usd: bid,
        pacing,
        value_usd: value,
        targeting,
        creative,
        status,
      });
      nav(`/cabinet/campaigns/${created.campaign_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not publish campaign");
      setPublishing(false);
    }
  };

  const setCr = (patch: Partial<Creative>) => setCreative((c) => ({ ...c, ...patch }));
  const resultLabel = est?.result_label ?? "results";

  const previewCreative = useMemo(
    () => ({ ...creative, brand_name: creative.brand_name || name }),
    [creative, name]
  );

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="crumb">Campaigns / New</div>
          <h1 className="page-title">Create a campaign</h1>
          <p className="page-sub">One page, a live estimate, and the exact card the network will show.</p>
        </div>
      </div>

      <div className="wizard">
        <div className="stack">
          {/* Objective */}
          <div className="card panel">
            <div className="panel-head">
              <div>
                <h3 className="panel-title">Objective</h3>
                <p className="panel-sub">What should this campaign optimize for?</p>
              </div>
            </div>
            <div className="obj-grid">
              {OBJECTIVES.map((o) => (
                <button
                  type="button"
                  key={o.key}
                  className={`obj-card ${objective === o.key ? "on" : ""}`}
                  onClick={() => pickObjective(o.key)}
                >
                  <div className="obj-name">
                    {o.name} <span className="mini-chip ghost">{o.stage}</span>
                  </div>
                  <div className="obj-desc">{o.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Basics */}
          <div className="card panel">
            <div className="panel-head">
              <h3 className="panel-title">Budget &amp; bid</h3>
            </div>
            <div className="form-grid">
              <div className="field">
                <label>Campaign name</label>
                <input
                  className="input"
                  placeholder="e.g. Spring launch"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="row-2">
                <div className="field">
                  <label>Daily budget</label>
                  <div className="input-usd">
                    <input
                      className="input"
                      type="number"
                      min={1}
                      value={budget}
                      onChange={(e) => setBudget(Math.max(0, parseFloat(e.target.value) || 0))}
                    />
                  </div>
                </div>
                <div className="field">
                  <label>Bid</label>
                  <div className="input-usd">
                    <input
                      className="input"
                      type="number"
                      min={0}
                      step="0.05"
                      value={bid}
                      onChange={(e) => setBid(Math.max(0, parseFloat(e.target.value) || 0))}
                    />
                  </div>
                  <span className="hint">{BID_HINT[objective]}</span>
                </div>
              </div>
              <div className="row-2">
                <div className="field">
                  <label>Pacing</label>
                  <div className="seg">
                    {(["even", "asap"] as const).map((p) => (
                      <button
                        key={p}
                        type="button"
                        className={`seg-btn ${pacing === p ? "on" : ""}`}
                        onClick={() => setPacing(p)}
                      >
                        {p === "even" ? "Even" : "ASAP"}
                      </button>
                    ))}
                  </div>
                  <span className="hint">
                    {pacing === "even" ? "Spread spend across the day" : "Spend as fast as it wins"}
                  </span>
                </div>
                {objective === "conversions" && (
                  <div className="field">
                    <label>Conversion value</label>
                    <div className="input-usd">
                      <input
                        className="input"
                        type="number"
                        min={0}
                        value={value}
                        onChange={(e) => setValue(Math.max(0, parseFloat(e.target.value) || 0))}
                      />
                    </div>
                    <span className="hint">Average order value — drives ROAS</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Targeting */}
          <div className="card panel">
            <div className="panel-head">
              <div>
                <h3 className="panel-title">Audience</h3>
                <p className="panel-sub">Leave a group empty to reach everyone in it.</p>
              </div>
            </div>
            <TargetingEditor value={targeting} onChange={setTargeting} options={options} />
          </div>

          {/* Creative */}
          <div className="card panel">
            <div className="panel-head">
              <h3 className="panel-title">Creative</h3>
            </div>
            <div className="form-grid">
              <div className="row-2">
                <div className="field">
                  <label>Brand name</label>
                  <input className="input" value={creative.brand_name} onChange={(e) => setCr({ brand_name: e.target.value })} />
                </div>
                <div className="field">
                  <label>Call to action</label>
                  <input className="input" value={creative.cta_text} onChange={(e) => setCr({ cta_text: e.target.value })} />
                </div>
              </div>
              <div className="field">
                <label>Headline</label>
                <input className="input" value={creative.title} onChange={(e) => setCr({ title: e.target.value })} />
              </div>
              <div className="field">
                <label>Body</label>
                <textarea className="textarea" value={creative.body} onChange={(e) => setCr({ body: e.target.value })} />
              </div>
              <div className="field">
                <label>Landing URL</label>
                <input
                  className="input"
                  placeholder="https://example.com"
                  value={creative.link_url}
                  onChange={(e) => setCr({ link_url: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Image</label>
                <div className="chip-set">
                  {STOCK.map((s) => (
                    <button
                      type="button"
                      key={s.key}
                      className={`chip-toggle ${creative.main_image_key === s.key ? "on" : ""}`}
                      onClick={() => setCr({ main_image_key: s.key })}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {error && <div className="err-line">{error}</div>}
          <div className="grid-actions">
            <button className="btn primary" disabled={!valid || publishing} onClick={() => publish("active")}>
              {publishing ? "Publishing…" : "Publish campaign"}
            </button>
            <button className="btn" disabled={!valid || publishing} onClick={() => publish("draft")}>
              Save as draft
            </button>
          </div>
        </div>

        {/* Sticky side: estimate + preview */}
        <div className="wizard-side">
          <div className="card panel">
            <div className="panel-head">
              <div>
                <h3 className="panel-title">Estimated daily delivery</h3>
                <p className="panel-sub">Projected with the same math the auction runs.</p>
              </div>
            </div>
            <div className="est-grid">
              <div className="est-item">
                <span className="est-num">{est ? compact(est.audience) : "—"}</span>
                <span className="est-lbl">Audience</span>
              </div>
              <div className="est-item">
                <span className="est-num">{est ? compact(est.impressions) : "—"}</span>
                <span className="est-lbl">Impressions / day</span>
              </div>
              <div className="est-item">
                <span className="est-num">{est ? compact(est.results) : "—"}</span>
                <span className="est-lbl">{resultLabel} / day</span>
              </div>
              <div className="est-item">
                <span className="est-num">{est ? usd(est.spend) : "—"}</span>
                <span className="est-lbl">Spend / day</span>
              </div>
              <div className="est-item">
                <span className="est-num">{est ? `${Math.round(est.win_rate * 100)}%` : "—"}</span>
                <span className="est-lbl">Win rate</span>
              </div>
            </div>
            {est?.budget_capped && (
              <div className="est-note">Budget-capped — demand exceeds the daily budget; raise it to deliver more.</div>
            )}
          </div>

          <div className="card panel">
            <div className="panel-head">
              <h3 className="panel-title">Preview</h3>
            </div>
            <CreativePreview creative={previewCreative} />
          </div>
        </div>
      </div>
    </div>
  );
}
