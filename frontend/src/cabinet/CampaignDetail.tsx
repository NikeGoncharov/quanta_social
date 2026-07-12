// One campaign, in full: the glass-box (why / learning / bid landscape) beside its reporting
// (KPIs / timeseries / breakdown), with inline edit, pause/resume, and delete. Live delivery
// comes from the shared SSE status; the diagnostics poll the runtime.
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  cabinetApi,
  type BidLandscape as BLData,
  type CampaignDetail as Detail,
  type Diagnosis,
  type KpiReport,
} from "../api/cabinet";
import { useSim } from "../hooks/SimContext";
import { BidLandscape } from "./BidLandscape";
import { BreakdownExplorer } from "./BreakdownExplorer";
import { CreativePreview } from "./CreativePreview";
import { EditCampaign } from "./EditCampaign";
import { OBJ_LABEL, usd } from "./format";
import { LearningBadge } from "./LearningBadge";
import { ReportKpis } from "./ReportKpis";
import { TimeseriesChart } from "./TimeseriesChart";
import { WhyPanel } from "./WhyPanel";

const REFRESH_MS = 6000;

export default function CampaignDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const { status } = useSim();

  const [detail, setDetail] = useState<Detail | null>(null);
  const [why, setWhy] = useState<Diagnosis | null>(null);
  const [land, setLand] = useState<BLData | null>(null);
  const [report, setReport] = useState<KpiReport | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const loadDetail = useCallback(async () => {
    try {
      setDetail(await cabinetApi.campaign(id));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
    }
  }, [id]);

  const loadLive = useCallback(() => {
    cabinetApi.why(id).then(setWhy).catch(() => {});
    cabinetApi.bidLandscape(id).then(setLand).catch(() => setLand(null));
    cabinetApi.kpis(id, 1440).then(setReport).catch(() => {});
  }, [id]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    loadLive();
    const t = setInterval(loadLive, REFRESH_MS);
    return () => clearInterval(t);
  }, [loadLive]);

  if (notFound) {
    return (
      <div className="page">
        <div className="empty-state">
          <h3>Campaign not found</h3>
          <Link className="btn" to="/cabinet/campaigns">
            Back to campaigns
          </Link>
        </div>
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="page">
        <p className="muted">Loading…</p>
      </div>
    );
  }

  const live = status?.lines.find((l) => l.ad_id === detail.ad_id) ?? null;

  const toggleStatus = async () => {
    const next = detail.status === "active" ? "paused" : "active";
    setDetail({ ...detail, status: next });
    try {
      await cabinetApi.patch(id, { status: next });
    } catch {
      /* reconciled by the reload below */
    }
    loadDetail();
    loadLive();
  };

  const del = async () => {
    try {
      await cabinetApi.remove(id);
      nav("/cabinet/campaigns");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed");
    }
  };

  const afterSave = () => {
    setEditing(false);
    loadDetail();
    loadLive();
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="crumb">
            <Link to="/cabinet/campaigns">Campaigns</Link> / {detail.name}
          </div>
          <h1 className="page-title">{detail.name}</h1>
          <div className="row-chips">
            <span className="mini-chip">{OBJ_LABEL[detail.objective]}</span>
            {detail.funnel_stage && <span className="mini-chip ghost">{detail.funnel_stage}</span>}
            <span className={`st-chip ${detail.status}`}>{detail.status}</span>
          </div>
        </div>
        <div className="grid-actions">
          <button className="btn" onClick={toggleStatus}>
            {detail.status === "active" ? "Pause" : "Activate"}
          </button>
          <button className="btn" onClick={() => setEditing((e) => !e)}>
            {editing ? "Close editor" : "Edit"}
          </button>
          <button className="btn" onClick={del}>
            Delete
          </button>
        </div>
      </div>

      {error && <div className="err-line">{error}</div>}

      {editing && <EditCampaign detail={detail} onSaved={afterSave} onCancel={() => setEditing(false)} />}

      <div className="detail-grid">
        <div className="stack">
          <WhyPanel why={why} />
          <ReportKpis report={report} />
          <TimeseriesChart campaignId={id} />
          <BreakdownExplorer campaignId={id} />
        </div>
        <div className="wizard-side">
          <LearningBadge live={live} />
          <BidLandscape data={land} />
          <div className="card panel">
            <div className="panel-head">
              <h3 className="panel-title">Creative</h3>
            </div>
            <CreativePreview creative={detail.creative} />
          </div>
          <div className="card panel">
            <div className="panel-head">
              <h3 className="panel-title">Setup</h3>
            </div>
            <div className="why-signals" style={{ border: "none", marginTop: 0, paddingTop: 0 }}>
              <div className="why-sig">
                <b>{usd(detail.daily_budget_usd)}</b>
                <span>Daily budget</span>
              </div>
              <div className="why-sig">
                <b>{usd(detail.bid_usd)}</b>
                <span>{detail.bid_label} bid</span>
              </div>
              <div className="why-sig">
                <b>{detail.pacing}</b>
                <span>Pacing</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
