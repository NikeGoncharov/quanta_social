// Inline edit for a campaign: budget / bid / value / pacing / targeting / creative. Objective
// is fixed after creation (it changes billing + learning semantics). Saves via PATCH.
import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import {
  cabinetApi,
  type CampaignDetail,
  type Creative,
  type TargetingOptions,
  type TargetingSpec,
} from "../api/cabinet";
import { CreativePreview } from "./CreativePreview";
import { TargetingEditor } from "./TargetingEditor";

export function EditCampaign({
  detail,
  onSaved,
  onCancel,
}: {
  detail: CampaignDetail;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [options, setOptions] = useState<TargetingOptions | null>(null);
  const [name, setName] = useState(detail.name);
  const [budget, setBudget] = useState(detail.daily_budget_usd);
  const [bid, setBid] = useState(detail.bid_usd);
  const [value, setValue] = useState(detail.value_usd);
  const [pacing, setPacing] = useState(detail.pacing);
  const [targeting, setTargeting] = useState<TargetingSpec>(detail.targeting);
  const [creative, setCreative] = useState<Creative>(detail.creative);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    cabinetApi.targetingOptions().then(setOptions).catch(() => {});
  }, []);

  const setCr = (patch: Partial<Creative>) => setCreative((c) => ({ ...c, ...patch }));

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await cabinetApi.patch(detail.campaign_id, {
        name: name.trim() || detail.name,
        daily_budget_usd: budget,
        bid_usd: bid,
        value_usd: value,
        pacing,
        targeting,
        creative,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
      setSaving(false);
    }
  };

  return (
    <div className="card panel">
      <div className="panel-head">
        <h3 className="panel-title">Edit campaign</h3>
      </div>
      <div className="detail-grid">
        <div className="form-grid">
          <div className="field">
            <label>Campaign name</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="row-2">
            <div className="field">
              <label>Daily budget</label>
              <div className="input-usd">
                <input className="input" type="number" min={1} value={budget} onChange={(e) => setBudget(Math.max(0, parseFloat(e.target.value) || 0))} />
              </div>
            </div>
            <div className="field">
              <label>{detail.bid_label} bid</label>
              <div className="input-usd">
                <input className="input" type="number" min={0} step="0.05" value={bid} onChange={(e) => setBid(Math.max(0, parseFloat(e.target.value) || 0))} />
              </div>
            </div>
          </div>
          <div className="row-2">
            <div className="field">
              <label>Pacing</label>
              <div className="seg">
                {(["even", "asap"] as const).map((p) => (
                  <button key={p} type="button" className={`seg-btn ${pacing === p ? "on" : ""}`} onClick={() => setPacing(p)}>
                    {p === "even" ? "Even" : "ASAP"}
                  </button>
                ))}
              </div>
            </div>
            {detail.objective === "conversions" && (
              <div className="field">
                <label>Conversion value</label>
                <div className="input-usd">
                  <input className="input" type="number" min={0} value={value} onChange={(e) => setValue(Math.max(0, parseFloat(e.target.value) || 0))} />
                </div>
              </div>
            )}
          </div>

          <div className="field">
            <label>Creative</label>
            <div className="row-2">
              <input className="input" placeholder="Brand" value={creative.brand_name} onChange={(e) => setCr({ brand_name: e.target.value })} />
              <input className="input" placeholder="CTA" value={creative.cta_text} onChange={(e) => setCr({ cta_text: e.target.value })} />
            </div>
            <input className="input" style={{ marginTop: 8 }} placeholder="Headline" value={creative.title} onChange={(e) => setCr({ title: e.target.value })} />
            <textarea className="textarea" style={{ marginTop: 8 }} placeholder="Body" value={creative.body} onChange={(e) => setCr({ body: e.target.value })} />
            <input className="input" style={{ marginTop: 8 }} placeholder="Landing URL" value={creative.link_url} onChange={(e) => setCr({ link_url: e.target.value })} />
          </div>

          <div>
            <label style={{ fontWeight: 700, fontSize: "0.82rem" }}>Audience</label>
            <div style={{ marginTop: 8 }}>
              <TargetingEditor value={targeting} onChange={setTargeting} options={options} />
            </div>
          </div>

          {error && <div className="err-line">{error}</div>}
          <div className="grid-actions">
            <button className="btn primary" disabled={saving} onClick={save}>
              {saving ? "Saving…" : "Save changes"}
            </button>
            <button className="btn" disabled={saving} onClick={onCancel}>
              Cancel
            </button>
          </div>
        </div>
        <div className="wizard-side">
          <div className="card panel">
            <div className="panel-head">
              <h3 className="panel-title">Preview</h3>
            </div>
            <CreativePreview creative={{ ...creative, brand_name: creative.brand_name || name }} />
          </div>
        </div>
      </div>
    </div>
  );
}
