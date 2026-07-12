// Typed client for the Quanta Ads cabinet API (Phase 3): accounts, campaigns CRUD + grid,
// wizard estimate, reporting, targeting, diagnostics.
import { req } from "./client";
import type { LineStatus } from "./sim";

export interface Account {
  id: string;
  name: string;
  currency: string;
  is_demo: boolean;
}

export type Objective = "awareness" | "traffic" | "engagement" | "conversions";
export type Pacing = "even" | "asap";
export type Status = "active" | "paused" | "draft";

export interface TargetingSpec {
  interests: string[];
  geos: string[];
  age_bands: string[];
  genders: string[];
}

export interface Creative {
  title: string;
  body: string;
  cta_text: string;
  brand_name: string;
  main_image_key: string;
  link_url: string;
}

export interface GridRow {
  campaign_id: string;
  ad_id: string;
  ad_set_id: string;
  account_id: string;
  name: string;
  brand: string;
  objective: Objective;
  funnel_stage: string | null;
  status: Status;
  pacing: Pacing;
  daily_budget: number;
  bid: number;
  bid_label: string;
  created_at: number;
  live: LineStatus | null; // present only for on-air (active) campaigns
}

export interface CampaignDetail {
  campaign_id: string;
  ad_id: string;
  ad_set_id: string;
  account_id: string;
  name: string;
  objective: Objective;
  funnel_stage: string | null;
  status: Status;
  pacing: Pacing;
  daily_budget_usd: number;
  bid_usd: number;
  bid_label: string;
  result_label: string;
  value_usd: number;
  targeting: TargetingSpec;
  creative: Creative;
  freq_cap_impressions: number | null;
  freq_cap_per_days: number;
  created_at: number;
}

export interface EstimateResult {
  audience: number;
  segments: number;
  auctions: number;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  revenue: number;
  win_rate: number;
  budget_capped: boolean;
  results: number;
  result_label: string;
}

export interface AudienceResult {
  audience: number;
  segments: number;
  population: number;
  reach_pct: number;
}

export interface TargetingOptions {
  interests: string[];
  geos: string[];
  age_bands: string[];
  genders: string[];
  population: number;
}

export interface Kpis {
  auctions: number;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  revenue: number;
  ctr: number | null;
  cvr: number | null;
  cpm: number | null;
  cpc: number | null;
  cpa: number | null;
  roas: number | null;
  win_rate: number | null;
}

export interface KpiReport {
  current: Kpis;
  previous: Kpis;
  deltas: Record<string, number | null>;
  window: number;
  anchor: number | null;
}

export interface BreakdownRow {
  value: string;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  revenue: number;
  ctr: number | null;
}

export interface Diagnosis {
  delivering: boolean;
  limiter: "audience" | "budget" | "frequency" | "bid" | "learning" | null;
  headline: string;
  detail: string;
  win_rate: number | null;
  audience: number;
  budget_util: number | null;
}

export interface BidPoint {
  multiplier: number;
  bid: number;
  win_rate: number;
  est_cpm: number | null;
  est_impressions: number;
  est_results: number;
  is_current: boolean;
}

export interface BidLandscape {
  campaign_id: string;
  objective: Objective;
  current_bid: number;
  bid_label: string;
  result_label: string;
  points: BidPoint[];
}

export interface CampaignCreate {
  name: string;
  objective: Objective;
  daily_budget_usd: number;
  bid_usd: number;
  pacing?: Pacing;
  value_usd?: number;
  targeting?: TargetingSpec;
  creative: Partial<Creative> & { title: string };
  freq_cap_impressions?: number | null;
  freq_cap_per_days?: number;
  account_id?: string;
  status?: Status;
}

export interface CampaignPatch {
  name?: string;
  status?: Status;
  daily_budget_usd?: number;
  pacing?: Pacing;
  bid_usd?: number;
  value_usd?: number;
  targeting?: TargetingSpec;
  creative?: Creative;
  freq_cap_impressions?: number | null;
  freq_cap_per_days?: number;
}

export interface EstimateBody {
  objective: Objective;
  daily_budget_usd: number;
  bid_usd: number;
  value_usd?: number;
  targeting?: TargetingSpec;
}

const qp = (o: Record<string, string | number | undefined>) => {
  const p = Object.entries(o)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return p.length ? `?${p.join("&")}` : "";
};

export const cabinetApi = {
  account: () => req<Account>("/cabinet/account"),
  accounts: () => req<{ accounts: Account[] }>("/cabinet/accounts"),

  grid: (accountId?: string) => req<{ rows: GridRow[] }>(`/cabinet/grid${qp({ account_id: accountId })}`),
  campaign: (id: string) => req<CampaignDetail>(`/cabinet/campaigns/${id}`),
  create: (body: CampaignCreate) =>
    req<CampaignDetail>("/cabinet/campaigns", { method: "POST", body: JSON.stringify(body) }),
  patch: (id: string, body: CampaignPatch) =>
    req<CampaignDetail>(`/cabinet/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: string) => req<void>(`/cabinet/campaigns/${id}`, { method: "DELETE" }),

  estimate: (body: EstimateBody) =>
    req<EstimateResult>("/cabinet/wizard/estimate", { method: "POST", body: JSON.stringify(body) }),

  targetingOptions: () => req<TargetingOptions>("/cabinet/targeting/options"),
  audience: (targeting: TargetingSpec) =>
    req<AudienceResult>("/cabinet/targeting/audience", {
      method: "POST",
      body: JSON.stringify({ targeting }),
    }),

  kpis: (campaignId?: string, window = 1440) =>
    req<KpiReport>(`/cabinet/reporting/kpis${qp({ campaign_id: campaignId, window })}`),
  timeseries: (campaignId?: string, bin = 30, window = 48) =>
    req<{ bin: number; points: import("./sim").DeliveryPoint[] }>(
      `/cabinet/reporting/timeseries${qp({ campaign_id: campaignId, bin, window })}`
    ),
  breakdown: (dimension: string, campaignId?: string, window = 1440) =>
    req<{ dimension: string; rows: BreakdownRow[] }>(
      `/cabinet/reporting/breakdown${qp({ dimension, campaign_id: campaignId, window })}`
    ),

  why: (id: string) => req<Diagnosis>(`/cabinet/campaigns/${id}/why`),
  bidLandscape: (id: string) => req<BidLandscape>(`/cabinet/campaigns/${id}/bid-landscape`),
};
