import { formSections } from "./formSchema";
import type { FieldDef } from "./formSchema";

/**
 * AI form-filling assistant.
 *
 * Given the partially-filled intake and the user's latest utterance, this
 * answers the currently-asked question (extracting a value into the field),
 * then asks the next unfilled field as a natural-language question.
 *
 * Uses a hosted LLM when OPENAI_API_KEY is set, otherwise a deterministic
 * keyword extractor so the flow works offline for the hackathon.
 */

export interface AssistantRequest {
  filled: Record<string, string>;
  asking?: string; // field key the user is currently answering
  utterance: string;
}

export interface AssistantResponse {
  reply: string;
  filled: Record<string, string>;
  next_field?: string;
  done: boolean;
}

const allFields: FieldDef[] = formSections.flatMap((s) => s.fields);

const YES_WORDS = /^(yes|yeah|yep|yup|true|sure|correct|right|do|did|i do|affirmative)\b/i;
const NO_WORDS = /^(no|nope|nah|false|wrong|don'?t|do not|i don'?t|negative|none)\b/i;

const ALIASES: Record<string, Record<string, string>> = {
  tenure: { renting: "Renting", rent: "Renting", owning: "Owning", own: "Owning" },
  owned_leased: { owned: "Owned", own: "Owned", lease: "Leased", leased: "Leased" },
  purchase_condition: { new: "New", used: "Used", demo: "Demo" },
  business_use: { yes: "Yes", no: "No" },
  winter_tires: { yes: "Yes", no: "No" },
  anti_theft: { yes: "Yes", no: "No" },
  held_other_classes: { yes: "Yes", no: "No" },
  retired: { yes: "Yes", no: "No" },
  cancellation_nonpayment: { yes: "Yes", no: "No" },
  licence_class: { g2: "G2", g1: "G", g: "G" },
  drive_type: { four: "4WD", awd: "AWD", fwd: "FWD", rwd: "RWD" },
  fuel_type: { gas: "Gas", petrol: "Gas", diesel: "Diesel", hybrid: "Hybrid", electric: "Electric" },
  sex: { male: "M", man: "M", m: "M", female: "F", woman: "F", f: "F" },
};

const MARITAL = { single: "S", married: "M", common: "C", partnership: "C", partner: "C", divorced: "D", separated: "S", widow: "W", widowed: "W" };

function asToken(s: string) {
  return s.replace(/[^a-z0-9]/gi, "").toLowerCase();
}

function matchSelect(field: FieldDef, utterance: string): string | undefined {
  const aliases = ALIASES[field.key] ?? {};
  const u = utterance.toLowerCase();
  for (const [alias, value] of Object.entries(aliases)) {
    if (u.includes(alias)) return value;
  }
  if (field.key === "marital_status") {
    for (const [alias, value] of Object.entries(MARITAL)) {
      if (u.includes(alias)) return value;
    }
  }
  if (field.key === "commute_days") {
    const n = /(\d)/.exec(utterance);
    if (n && Number(n[1]) >= 0 && Number(n[1]) <= 7) return n[1];
  }
  // Boolean-ish fields: answer yes/no.
  if (field.options?.length === 2 && (field.options[0] === "Yes" || field.options[0] === "No")) {
    if (YES_WORDS.test(utterance)) return "Yes";
    if (NO_WORDS.test(utterance)) return "No";
  }
  // Direct option substring match.
  for (const opt of field.options ?? []) {
    if (u.includes(asToken(opt))) return opt;
  }
  return undefined;
}

const MONTHS: Record<string, number> = {
  january: 1, february: 2, march: 3, april: 4, may: 5, june: 6, july: 7,
  august: 8, september: 9, october: 10, november: 11, december: 12,
  jan: 1, feb: 2, mar: 3, apr: 4, jun: 6, jul: 7, aug: 8,
  sep: 9, sept: 9, oct: 10, nov: 11, dec: 12,
};

const NUM_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17,
  eighteen: 18, nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70,
  eighty: 80, ninety: 90, thousand: 1000, zero: 0, oh: 0,
  // ordinal day words (for "fourteenth of October", "twenty first", etc.)
  first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7, eighth: 8, ninth: 9,
  tenth: 10, eleventh: 11, twelfth: 12, thirteenth: 13, fourteenth: 14, fifteenth: 15,
  sixteenth: 16, seventeenth: 17, eighteenth: 18, nineteenth: 19, twentieth: 20, thirtieth: 30,
};

// Convert spoken numbers like "twenty one" / "fourteenth" / "1984" into digits.
function wordToNumber(t: string): number | undefined {
  const s = t.trim().toLowerCase().replace(/[^a-z ]/g, "");
  if (!s) return undefined;
  const parts = s.split(/\s+/);
  const unit = NUM_WORDS[parts[0]];
  if (parts.length === 1 && unit !== undefined) return unit;
  if (parts.length === 2 && unit !== undefined && NUM_WORDS[parts[1]] !== undefined) {
    return unit + NUM_WORDS[parts[1]];
  }
  // "nineteen eighty four" -> 1984 ; "twenty twenty four" -> 2024
  const isTeen = unit !== undefined && unit >= 13 && unit <= 19;
  const isDecade = unit !== undefined && unit >= 20 && unit <= 90 && unit % 10 === 0;
  if (parts.length === 3 && (isTeen || isDecade)) {
    const tens = NUM_WORDS[parts[1]];
    const ones = NUM_WORDS[parts[2]];
    if (tens !== undefined && ones !== undefined && (isTeen || tens % 10 === 0)) {
      return unit * 100 + tens + ones;
    }
  }
  // "two thousand six" -> 2006
  if (parts.length === 3 && unit !== undefined && NUM_WORDS[parts[1]] === 1000 && NUM_WORDS[parts[2]] !== undefined) {
    return unit * 1000 + NUM_WORDS[parts[2]];
  }
  // "two thousand" -> 2000
  if (parts.length === 2 && unit !== undefined && NUM_WORDS[parts[1]] === 1000) return unit * 1000;
  return undefined;
}

function parseDate(t: string): string | undefined {
  // Normalize: strip punctuation, ordinal suffixes (14th -> 14).
  const clean = t
    .toLowerCase()
    .replace(/[.,;:!]/g, " ")
    .replace(/\b(\d{1,2})(?:st|nd|rd|th)\b/g, "$1")
    .replace(/\s+/g, " ")
    .trim();

  // Numeric forms: 1984-10-14, 1984/10/14, 10/14/1984, 14/10/1984.
  const iso = /(\d{4})[-/](\d{1,2})[-/](\d{1,2})/.exec(clean);
  if (iso) {
    return `${iso[1]}-${iso[2].padStart(2, "0")}-${iso[3].padStart(2, "0")}`;
  }
  const slash = /(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})/.exec(clean);
  if (slash) {
    const a = parseInt(slash[1]), b = parseInt(slash[2]), y = slash[3].length === 2 ? "20" + slash[3] : slash[3];
    const month = a > 12 ? b : a;
    const day = a > 12 ? a : b;
    return `${y}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  const words = clean.split(/\s+/);
  const monthIdx = words.findIndex((w) => MONTHS[w]);
  if (monthIdx >= 0) {
    const month = MONTHS[words[monthIdx]];
    // Find the year: a 4-digit year, or a spoken year ("nineteen eighty four").
    let year: number | undefined;
    const yearIdx = words.findIndex((w) => /^(19|20)\d{2}$/.test(w));
    if (yearIdx >= 0) {
      year = parseInt(words[yearIdx]);
    } else {
      for (let i = 0; i < words.length; i++) {
        const three = wordToNumber(words.slice(i, i + 3).join(" "));
        if (three !== undefined && three >= 1900 && three <= 2100) {
          year = three;
          break;
        }
        const two = wordToNumber(words.slice(i, i + 2).join(" "));
        if (two !== undefined && two >= 1900 && two <= 2100) {
          year = two;
          break;
        }
      }
      if (year === undefined) {
        const single = wordToNumber(words.join(" "));
        if (single !== undefined && single >= 1900 && single <= 2100) year = single;
      }
    }
    if (year === undefined) return undefined;

    // Day: the standalone number that isn't the year, or a spoken number.
    let day: number | undefined;
    const dayNum = words.find((w) => /^\d{1,2}$/.test(w) && parseInt(w) !== year);
    if (dayNum !== undefined) {
      day = parseInt(dayNum);
    } else {
      for (const w of words) {
        const n = wordToNumber(w);
        if (n !== undefined && n >= 1 && n <= 31 && n !== year) { day = n; break; }
      }
    }
    if (day === undefined) return undefined;
    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  // "14th of October 1984" — ordinal already stripped; month may come after day.
  return undefined;
}

function extractValue(field: FieldDef, utterance: string): string | undefined {
  const t = utterance.trim();
  if (!t) return undefined;
  switch (field.type) {
    case "select":
      return matchSelect(field, t);
    case "number": {
      const m = /-?\d+(\.\d+)?/.exec(t);
      return m ? m[0] : undefined;
    }
    case "email": {
      const m = /[\w.+-]+@[\w-]+\.[\w.]+/.exec(t);
      return m ? m[0] : undefined;
    }
    case "tel": {
      const digits = t.replace(/\D/g, "");
      return digits.length >= 7 ? digits : undefined;
    }
    case "date": {
      return parseDate(t);
    }
    default:
      // Free text: use the whole answer, but drop common conversational filler.
      if (YES_WORDS.test(t) || NO_WORDS.test(t)) return undefined;
      return t.replace(/^that'?s\s+|^it'?s\s+/i, "");
  }
}

function questionFor(field: FieldDef): string {
  const hint =
    field.type === "select" && field.options?.length ? ` (${field.options.join(" / ")})` : "";
  const label = field.label.replace(/[?.]$/, "").toLowerCase();
  return `What is your ${label}?${hint}`;
}

export function runAssistant(req: AssistantRequest): AssistantResponse {
  const filled = { ...req.filled };

  if (req.asking) {
    const field = allFields.find((f) => f.key === req.asking);
    if (field) {
      const value = extractValue(field, req.utterance);
      if (value) {
        filled[field.key] = value;
      } else {
        return {
          reply: `I didn't catch that. ${questionFor(field)}`,
          filled,
          next_field: field.key,
          done: false,
        };
      }
    }
  }

  const nextField = allFields.find((f) => !filled[f.key]);
  if (!nextField) {
    return { reply: "That's everything — getting your quotes now.", filled, done: true };
  }
  return {
    reply: questionFor(nextField),
    filled,
    next_field: nextField.key,
    done: false,
  };
}

export async function runLLMAssistant(
  req: AssistantRequest,
  apiKey: string | undefined
): Promise<AssistantResponse | null> {
  if (!apiKey) return null;
  const schema = formSections.map((s) => ({
    section: s.title,
    fields: s.fields.map((f) => ({ key: f.key, label: f.label, type: f.type, options: f.options ?? [], required: !!f.required })),
  }));
  try {
    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        temperature: 0,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "system",
            content:
              "You are an insurance intake assistant. You receive the form schema, the fields already filled, and the user's latest utterance. " +
              "Reply with JSON: {\"extracted\": {\"<field_key>\": \"<value>\"}} mapping values you can confidently parse from the utterance into the correct schema field keys, and " +
              "{\"next_field\": \"<field_key or null>\"} naming the first unfilled required-or-relevant field to ask next. Use exact option strings from the schema. " +
              "Do not invent values. If the user answered a yes/no or option field, map to the exact option string.",
          },
          {
            role: "user",
            content: JSON.stringify({
              schema,
              filled: req.filled,
              currently_asking: req.asking,
              utterance: req.utterance,
            }),
          },
        ],
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const parsed = JSON.parse(data.choices?.[0]?.message?.content ?? "{}");
    const filled = { ...req.filled };
    for (const [k, v] of Object.entries(parsed.extracted ?? {})) {
      if (typeof v === "string" && v.length) filled[k] = v;
    }
    const next = parsed.next_field ?? allFields.find((f) => !filled[f.key])?.key;
    if (!next) return { reply: "That's everything — getting your quotes now.", filled, done: true };
    const f = allFields.find((x) => x.key === next);
    return { reply: questionFor(f ?? { key: next, label: next, type: "text" }), filled, next_field: next, done: false };
  } catch {
    return null;
  }
}
