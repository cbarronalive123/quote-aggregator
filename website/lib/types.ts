export type DistributionType =
  | "direct"
  | "exclusive_agent"
  | "broker"
  | "aggregator"
  | "affinity"
  | "MGA_program"
  | "mutual"
  | "residual";

export type ProductScope =
  | "standard_PPA"
  | "nonstandard_PPA"
  | "high_net_worth"
  | "collector"
  | "commercial_specialty"
  | "unknown";

export type QuoteStatus =
  | "quoted_comparable"
  | "quoted_non_comparable"
  | "estimate_only"
  | "callback_required"
  | "manual_handoff"
  | "ineligible"
  | "affinity_restricted"
  | "specialty_only"
  | "duplicate_rate_source"
  | "not_currently_writing"
  | "blocked"
  | "unreachable"
  | "unresolved";

export interface MarketRecord {
  registry_id: string;
  legal_underwriter: string;
  insurer_group: string;
  brand_or_program: string;
  distribution_type: DistributionType;
  product_scope: ProductScope;
  distinct_rate_source_id?: string;
  quote_url?: string;
  public_phone_route?: string;
  // E.164 number to call when this carrier only quotes by phone (phone agent target).
  phone?: string;
  licensed_intermediary?: string;
  requirements?: string[];
  automation_notes?: string;
  status: QuoteStatus;
  source_url?: string;
  last_verified_at?: string;
  evidence_artifact?: string;
}

export interface QuoteOutcome {
  registry_id: string;
  brand: string;
  logo?: string;
  status: QuoteStatus;
  annual_premium?: number;
  monthly_premium?: number;
  quote_id?: string;
  effective_date?: string;
  expiry_date?: string;
  coverage_notes?: string;
  discounts?: string[];
  confidence: "high" | "medium" | "low";
  timestamp: string;
  evidence?: string;
  // Source of the premium. "automated" = browser automation; "phone" = a parsed call
  // recording from the phone agent. When "phone", `recording` links the audio to play.
  source?: "automated" | "phone";
  recording?: string;
}

export interface Profile {
  person: Record<string, any>;
  auto: Record<string, any>;
  current_insurance: Record<string, any>;
}

export interface CallRecord {
  id: string;
  registry_id: string;
  brand: string;
  direction: "outbound" | "inbound";
  status: QuoteStatus;
  recording_path?: string;
  transcript?: string;
  outcome_notes?: string;
  timestamp: string;
}
