// Typed client for the Quanta Ads sim + RTB inspector API (Phase 2).
import { req } from "./client";

export interface LineStatus {
  ad_id: string;
  campaign_id: string;
  brand: string;
  name: string;
  objective: "awareness" | "traffic" | "engagement" | "conversions";
  funnel_stage: string | null;
  pacing: "even" | "asap";
  daily_budget: number;
  spent_today: number;
  budget_util: number | null;
  in_learning: boolean | null;
  signal: number | null;
  signal_to_exit: number | null;
}

export interface SimStatus {
  running: boolean;
  active: boolean;
  viewers: number;
  speed: number;
  tick_hz: number;
  sim_time: number;
  sim_day: number;
  sim_clock: string;
  market_density: number;
  lines: LineStatus[];
}

export interface DeliveryPoint {
  t: number;
  auctions: number;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  revenue: number;
}

export interface BidRow {
  seat: string;
  price: number;
  price_micros: number;
  crid?: string;
  cid?: string;
  adomain?: string[];
  is_winner?: boolean;
  reason?: string;
  reason_code?: number;
}

export interface NoticeRow {
  kind: string;
  seat: string;
  url: string;
  billed: boolean;
}

export interface SampleSummary {
  id: number;
  sim_time: number;
  segment_key: string;
  line_ad_id: string;
  won: boolean;
  winner_seat: string;
  winner_ad_id: string;
  clearing: number;
  floor: number;
  min_to_win: number;
  eligible_count: number;
  filtered_count: number;
}

export interface SampleDetail {
  id: number | null;
  sim_time: number;
  segment_key: string;
  line_ad_id: string;
  won: boolean;
  winner_seat: string;
  winner_ad_id: string;
  clearing: number;
  floor: number;
  min_to_win: number;
  request: Record<string, unknown>;
  bids: { eligible: BidRow[]; filtered: BidRow[] };
  notices: NoticeRow[];
}

export interface ControlPatch {
  running?: boolean;
  speed?: number;
  market_density?: number;
}

export const simApi = {
  status: () => req<SimStatus>("/sim/status"),
  control: (patch: ControlPatch) =>
    req<SimStatus>("/sim/control", { method: "POST", body: JSON.stringify(patch) }),
  delivery: (window = 180) =>
    req<{ points: DeliveryPoint[] }>(`/sim/delivery?window=${window}`),
  samples: (limit = 40) => req<{ samples: SampleSummary[] }>(`/sim/rtb/samples?limit=${limit}`),
  sample: (id: number) => req<SampleDetail>(`/sim/rtb/samples/${id}`),
  replay: (body: { ad_id?: string; segment_key?: string } = {}) =>
    req<SampleDetail>("/sim/rtb/replay", { method: "POST", body: JSON.stringify(body) }),
};
