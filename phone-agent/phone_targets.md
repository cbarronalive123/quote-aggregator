# Ontario Phone-Quote Targets

Carriers and brokerages in **Ontario** that will give a car-insurance quote **over the phone**.
These are the routes the phone agent (`POST /api/call`) should reach when a carrier won't
quote through browser automation.

Numbers were researched online (Aug 2026). **Always confirm the number and the "do you write
Ontario private passenger auto" eligibility before running the AI agent against them.** Several
of these are licensed-broker routes and will ask to speak to a person or broker.

> Compliance note: some entries (Facility Association, Echelon) do **not** quote consumers
> directly — they route through a licensed broker. Call the broker lines listed below.

---

## 0. AI-voice reception (researched Aug 2026)

No Ontario insurer/broker publicly says it **accepts outbound AI-agent calls for quotes**.
The AI-voice work in the market runs the *other* way: carriers/brokers deploy their own AI voice
agents to quote **their** customers. Realistic expectations:

- **AI-voice-native (most likely to tolerate an AI, but still route to a human):** Excalibur
  Insurance ("Aiden" AI quoting, IBAO member, works with Wawanesa), Aviva Canada (voice quoting),
  Wawanesa, onlia / Southampton Financial (FUTR AI Agent App).
- **Broker-only lines (expect refusal or `manual_handoff`):** Echelon, Coachman, Facility
  Association, and the mutuals — licensed brokers will likely insist on speaking to the named
  applicant for consent/identity.
- **Compliance:** FCC (Feb 2024) treats an AI-generated voice as an "artificial or prerecorded
  voice" under the TCPA; outbound AI calls generally require prior express written consent, DNC
  scrubbing, identification and an opt-out ($500–$1,500/call). As the *caller* dialing a business
  quote line the posture differs from soliciting a consumer, but expect human agents to gate on
  applicant consent. The agent prompt already discloses AI and offers to transfer.

## 1. Broker-only / non-standard insurers (best "phone-only" fits)

| Brand | Phone (E.164) | Channel | Notes |
|---|---|---|---|
| Echelon Insurance | `+18003243566` | Broker-only | Non-standard / high-risk auto. Broker required; head office answers, routes to broker. Claims ON/AB/Atlantic: `+18662522854`. Direct (Mississauga): `+19052147880`. |
| Coachman (SGI Canada) | `+14162553417` | Broker | Non-standard; current insurer in the demo profile. Broker line. |
| Facility Association | `+18002689572` | Via broker | Insurer of last resort. Consumers must contact a licensed broker; no direct consumer quoting. FA general: `+14168631750`. |

## 2. Ontario Mutuals (quote via local agent/broker by phone)

Independent Ontario mutuals often quote only through a local agent/broker line. Verify the
mutual covers the applicant's address before calling.

| Brand | Phone (E.164) |
|---|---|
| Ayr Farmers Mutual | `+18002658792` / `+15196327413` |
| Cayuga Mutual | `+18005673381` / `+19057725498` |
| The Commonwell Mutual | `+17053242146` |
| Peel Mutual | `+18002683069` / `+19054512386` |
| Heartland Farm Mutual | `+18002658813` |
| Edge Mutual | `+15196383304` / `+18446383305` |
| Axiom Mutual | `+15192364381` |
| L & A Mutual | `+16133544810` |
| Erie Mutual | `+19057748566` |
| Bay of Quinte Mutual | `+16134762145` |
| Kent & Essex Mutual | `+15193523190` |
| Trillium Mutual | `+15196552011` |
| Salus Mutual | `+15197623530` |
| Westminster Mutual | `+15196441663` |
| Yarmouth Mutual | `+15196311572` |
| Grenville Mutual | `+16132589988` |
| Usborne & Hibbert Mutual | `+15192350350` |
| Dufferin Mutual | `+15199252026` |
| Brant Mutual | `+15197520088` |
| Lambton Mutual | `+15198762304` |
| Caradoc Townsend Mutual | `+15194437231` |
| Amherst Island Mutual | `+16133892012` |
| Algoma Mutual | `+17058423345` |

Full directory: <https://www.ontariomutuals.ca/findyourmutual> and <https://omia.com/mutual-directory/>

## 3. Brokerages / aggregators that quote by phone

RIB-licensed brokers that will shop Ontario auto by phone.

| Brand | Phone (E.164) | Notes |
|---|---|---|
| isure | `+18775147873` | Also `+18776892957`. |
| Regal Insurance (Brantford) | `+18005166276` | |
| onlia | `+18444727905` | |
| Rates.ca | `+18447260907` | |
| LowestRates.ca | `+18554876911` | |
| insurancehotline.com | `+18558217312` | |
| Surex | `+18552426612` | |
| ThinkInsure | `+18555505515` | Echelon + non-standard specialist. |
| Scoop Insurance | `+14165852918` | |
| Mitch Insurance | `+18007312228` | Non-standard / high-risk specialist (Echelon, Facility). |

## 4. Direct insurers that also accept phone quotes (Ontario)

Have online quoting too, but a human can quote by phone.

| Brand | Phone (E.164) | Notes |
|---|---|---|
| Intact / belairdirect | `+18553881771` | New-client quote line. |
| CAA South Central Ontario | `+18336999769` | |
| Square One | `+18553316933` | |
| Aviva | `+18003874518` | AI-voice native (voice quoting via ProNavigator). |
| Desjardins | `+18668384677` | |
| TD Insurance | `+18883362627` | |

## 5. AI-voice-native brokers (best starting points for an AI agent)

| Brand | Phone (E.164) | Notes |
|---|---|---|
| Excalibur Insurance (Clinton/Exeter/Mitchell, ON) | `+18882987343` | IBAO member; built "Aiden" AI voice/chat auto & home quoting (with Wawanesa + ProNavigator). Most AI-receptive found. |
| Aviva Canada | `+18003874518` | Voice quoting via Google Home/ProNavigator (Ontario only). |
| Wawanesa | `+18003612528` | Voice quoting through brokers (Excalibur/ProNavigator). |
| onlia (Southampton Financial) | `+18444727905` | Parent launched bindable AI-quoting "FUTR" app in Ontario. |

---

## Recommended call order (phone-only first)

1. Non-standard/broker-only: **Echelon**, **Coachman**, **Facility Association (via broker)**.
2. Ontario **mutuals** that cover the garaging address.
3. Broker **aggregators** (isure, ThinkInsure, Mitch, Rates.ca) — one call can shop several carriers.
4. Direct insurers that accept phone quotes as a fallback.

Machine-readable copy: [`phone_targets.json`](./phone_targets.json).
