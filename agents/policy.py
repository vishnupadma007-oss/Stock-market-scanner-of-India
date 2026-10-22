"""Policy Impact analyst: when a regulator or the government changes the rules, who gets hit and
who benefits?

Example that shaped it: on 24 Sep 2026 IRDAI proposed caps on insurance commissions and
PolicyBazaar (PB Fintech) fell 36% in a day, while banks earning bancassurance fees also face
lower distribution income. Markets reprice such news within minutes, so a rulebook gives the
first answer instantly; Claude then reasons through second-order effects (see the
`policy-impact` skill) when a POLICY event wakes it.

Each rule: a headline pattern (the regulator/measure), and the impact on our F&O stocks:
direction (+1 benefits / -1 hurt), strength (1 small, 2 clear, 3 direct hit to the business
model) and why. Proposals and consultation papers count, final rules count more; a rule that
names a company in the headline hits that company directly.
"""
import re

from .intel import symbols_in
from .sector_results import GROUPS

BANKS = GROUPS["bank"]
PRIVATE_BANKS = ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "INDUSINDBK", "IDFCFIRSTB", "FEDERALBNK", "AUBANK"]
NBFCS = GROUPS["nbfc"]
IT = GROUPS["it"]
AUTOS = GROUPS["auto"]
PHARMA = GROUPS["pharma"]
STEEL = ["TATASTEEL", "JSWSTEEL", "SAIL"]
OMCS = ["BPCL", "IOC"]
DEFENCE = ["HAL", "BEL", "BHEL"]

# (name, headline pattern, {symbols: (direction, strength, why)})
RULES = [
    ("IRDAI distribution/commission caps",
     r"irdai.*(commission|distribution|intermediar|broker|bancassurance|expense of management|clawback)|"
     r"(commission|distribution).*(cap|overhaul|recalibrat).*insur",
     {**{s: (-1, 3, "insurance distribution is the core business; commission caps cut revenue per policy")
         for s in ["POLICYBZR"]},
      **{s: (-1, 1, "bancassurance fee income falls with lower commissions") for s in PRIVATE_BANKS + ["SBIN"]}}),
    ("IRDAI action / insurance rules (general)",
     r"\birdai\b.*(rule|norm|guideline|regulation|proposal|draft|penalt|fine)",
     {"POLICYBZR": (-1, 1, "insurance aggregator under IRDAI rules")}),
    ("RBI repo rate cut",
     r"(rbi|monetary policy|mpc).*(cuts?|reduc|lower)\w*.*(repo|rates?|policy rate)|repo rate cut|rate cut by rbi",
     {**{s: (1, 2, "lower borrowing costs widen NBFC spreads and lift loan demand") for s in NBFCS},
      **{s: (1, 1, "cheaper loans support vehicle demand") for s in AUTOS},
      "DLF": (1, 2, "home-loan rates fall: housing demand and developer valuations rise"),
      **{s: (-1, 1, "loan yields reprice faster than deposits: near-term margin (NIM) pressure") for s in BANKS}}),
    ("RBI repo rate hike",
     r"(rbi|monetary policy|mpc).*(hikes?|raise|increase)\w*.*(repo|rates?|policy rate)|repo rate hike",
     {**{s: (-1, 2, "higher funding costs squeeze NBFC spreads") for s in NBFCS},
      "DLF": (-1, 2, "dearer home loans weigh on housing demand"),
      **{s: (-1, 1, "costlier vehicle loans") for s in AUTOS}}),
    ("RBI CRR cut / liquidity boost",
     r"\bcrr\b.*(cut|reduc|lower)|(cut|reduc|lower)\w*.*\bcrr\b|rbi.*liquidity (infusion|boost)|open market (purchase|operation)",
     {s: (1, 2, "more lendable money and lower cost of deposits") for s in BANKS}),
    ("RBI risk weights / unsecured lending curbs",
     r"risk weights?.*(raise|hike|increase|higher)|(unsecured|consumer|personal) (loans?|credit).*(curb|tighten|risk weight)|"
     r"rbi.*(tighten|curb).*(lending|loans)",
     {**{s: (-1, 2, "more capital needed per consumer loan: slower growth") for s in ["BAJFINANCE", "SHRIRAMFIN", "CHOLAFIN", "PAYTM"]},
      **{s: (-1, 1, "unsecured loan growth slows") for s in PRIVATE_BANKS}}),
    ("RBI revolving credit / card rules",
     r"(revolving credit|credit card|buy now pay later|bnpl).*(ban|curb|rule|draft|restrict)",
     {"BAJFINANCE": (-1, 1, "consumer lending products reworked"), "PAYTM": (-1, 1, "lending distribution affected")}),
    ("SEBI derivatives (F&O) curbs",
     r"sebi.*(f&o|futures and options|derivative|expiry|lot size|options trading).*(curb|tighten|restrict|new rules|framework)",
     {"PAYTM": (-1, 1, "broking arm volumes fall with F&O curbs")}),
    ("Telecom tariff hike",
     r"(telecom|mobile|jio|airtel|vodafone|\bvi\b|prepaid|postpaid).*(tariff|plan price).*(hike|increase|raise)|"
     r"(jio|airtel|vodafone|telcos?).*(raise|hike|increase).*(tariff|price)",
     {"BHARTIARTL": (1, 2, "higher ARPU flows straight to earnings")}),
    ("GST rate cut on autos",
     r"\bgst\b.*(cut|reduc|lower).*(car|vehicle|auto|two-wheeler)|(car|vehicle|auto|two-wheeler).*\bgst\b.*(cut|reduc|lower)",
     {s: (1, 2, "lower on-road prices lift volumes") for s in AUTOS}),
    ("GST rate cut on cement",
     r"\bgst\b.*(cut|reduc|lower).*cement|cement.*\bgst\b.*(cut|reduc|lower)",
     {s: (1, 2, "lower tax on cement lifts demand and pricing room") for s in ["ULTRACEMCO", "GRASIM"]}),
    ("GST rate cut on consumer goods",
     r"\bgst\b.*(cut|reduc|lower).*(fmcg|consumer|food|packaged|soap|biscuit)",
     {s: (1, 1, "lower prices support volumes") for s in ["HINDUNILVR", "NESTLEIND", "BRITANNIA", "ITC"]}),
    ("Gold import duty cut / hike",
     r"(customs|import) duty.*gold|gold.*(customs|import) duty",
     {"TITAN": (0, 1, "jewellery demand moves with gold duty (cut helps, hike hurts)")}),
    ("Steel import curbs / safeguard duty",
     r"(safeguard|anti-dumping|import) duty.*steel|steel.*(safeguard|anti-dumping)|curb.*steel imports",
     {s: (1, 2, "protection from cheap imports supports Indian steel prices") for s in STEEL}),
    ("Windfall tax on crude",
     r"windfall (tax|gains tax)",
     {"ONGC": (-1, 2, "windfall tax cuts realised crude price"), "RELIANCE": (-1, 1, "export levy on fuels")}),
    ("Fuel excise duty / price changes",
     r"excise duty.*(petrol|diesel|fuel)|(petrol|diesel).*(price cut|price hike|excise)",
     {s: (0, 1, "marketing margins move with retail fuel prices and duties") for s in OMCS}),
    ("Electronics PLI / manufacturing incentives",
     r"\bpli\b|production[- ]linked incentive|electronics manufacturing scheme",
     {"DIXON": (1, 2, "direct beneficiary of electronics manufacturing incentives")}),
    ("Defence procurement approvals",
     r"(defence acquisition council|\bdac\b|defence ministry|mod).*(approv|clear|sanction|order)|defence (procurement|capex|budget)",
     {s: (1, 2, "more domestic defence orders") for s in DEFENCE}),
    ("US H-1B / visa curbs",
     r"h-?1b|visa (fee|curb|restriction)|outsourcing (tax|curb)|hire act",
     {s: (-1, 2, "higher onsite costs and US demand risk for IT services") for s in IT}),
    ("US tariffs on pharma / USFDA",
     r"(tariff|duty).*(pharma|drug|generic)|(pharma|drug|generic).*(tariff|duty)",
     {s: (-1, 2, "US generics exposure") for s in PHARMA}),
    ("Infrastructure / railway capex push",
     r"(railway|infrastructure|capex|road) (budget|allocation|spending|push)|national infrastructure pipeline",
     {s: (1, 1, "more project orders") for s in ["LT", "BHEL"]}),
    ("Power demand / tariff policy",
     r"(power|electricity) (demand|tariff).*(record|policy|cerc|hike)|\bcerc\b",
     {s: (1, 1, "higher demand / regulated returns") for s in ["NTPC", "POWERGRID", "TATAPOWER"]}),
    ("Coal import curbs",
     r"coal (import|imports).*(curb|restrict|cut|duty)",
     {"COALINDIA": (1, 2, "domestic coal demand rises")}),
]

# A regulator acting against a company named in the headline hits that company directly.
ENFORCEMENT = r"\b(rbi|sebi|irdai|trai|ed|cbi|income tax|nclt|cci|usfda)\b.*" \
              r"(bars?|bans?|penal|fine[sd]?|restrict|probe|raid|warning letter|show cause|order|action|curb|halt)"
UPGRADE = r"\b(rbi|sebi|irdai|usfda)\b.*(lifts?|removes?|eases?|withdraws?) (curbs?|restrictions?|ban)|" \
          r"usfda.*(clean chit|eir|no observations|approval)"


# Right after the measure, in the same clause: "visa curbs NOT TARGETED at India" reverses it.
REVERSED = r"^[^;,.:|]{0,25}\b(not targeted|rules? out|no plans?|den(y|ies|ied)|scrapp|withdraw|roll(s|ed)? back|put on hold)"
# Delay or softening of a measure already known: mild relief for those it hits, not a new blow.
SOFTENING = r"\b(extend\w*|more time|deadline extended)\b.{0,30}\b(feedback|consultation|comment|deadline|period)|" \
            r"\b(defer\w*|delay\w*|postpon\w*|put on hold|phased|gradual (reset|implementation|rollout)|soften\w*|" \
            r"reconsider\w*|relief|dilut\w*|rollback|roll back)\b"
# Talk, not action: "RBI may need to raise rates", "RBI weighs a ban". (Formal proposals and
# draft rules keep full weight: IRDAI's consultation paper alone cut PolicyBazaar by a third.)
TALK = r"\b(may|might|could|weighs?|mulls?|consider(s|ing)?|need to|expected to|likely|unlikely|seeks? to calm|explain|what does)\b"


def assess(headline: str) -> list[dict]:
    """Impacts of one headline on our stocks: [{symbol, direction, strength, why, rule}]."""
    impacts = {}
    talk = bool(re.search(TALK, headline, re.I))
    softening = bool(re.search(SOFTENING, headline, re.I))
    for name, pattern, effects in RULES:
        m = re.search(pattern, headline, re.I)
        if m:
            reversed_ = bool(re.search(REVERSED, headline[m.end():], re.I))
            for sym, (direction, strength, why) in effects.items():
                if direction == 0:  # the headline says which way: cut helps, hike hurts
                    direction = 1 if re.search(r"\b(cut|reduc|lower|eas)", headline, re.I) else -1
                if reversed_ or softening:
                    direction, strength = -direction, 1
                    why = f"{'reversed or denied' if reversed_ else 'delayed or softened'}: {why}"
                elif talk:
                    strength, why = max(1, strength - 1), f"talk, not yet action: {why}"
                prev = impacts.get(sym)
                if prev is None or strength > prev["strength"]:
                    impacts[sym] = {"symbol": sym, "direction": direction, "strength": strength, "why": why, "rule": name}
    named = symbols_in(headline)
    if named and re.search(ENFORCEMENT, headline, re.I) and not re.search(UPGRADE, headline, re.I):
        for sym in named:
            impacts[sym] = {"symbol": sym, "direction": -1, "strength": 2 if talk else 3,
                            "why": "regulator acting against the company" + (" (talk, not yet action)" if talk else ""),
                            "rule": "Regulatory action on a named company"}
    elif named and re.search(UPGRADE, headline, re.I):
        for sym in named:
            impacts[sym] = {"symbol": sym, "direction": 1, "strength": 2, "why": "regulator easing curbs / clearing the company",
                            "rule": "Regulator relief for a named company"}
    return list(impacts.values())


def to_intel(item: dict, impacts: list[dict]) -> list[dict]:
    """Policy impacts as intelligence-log items for the Data Analyzer (one per affected stock)."""
    from . import intel
    out = []
    for imp in impacts:
        out.append(intel.make_item(
            id=f"policy-{item['id']}-{imp['symbol']}", time=item["time"], source=f"Policy rules ({item['source']})",
            kind="policy", symbols=[imp["symbol"]], category=imp["rule"],
            sentiment=round(imp["direction"] * imp["strength"] / 3, 2), impact=imp["strength"],
            headline=f"{imp['rule']}: {imp['why']} | {item['headline'][:160]}", url=item.get("url", "")))
    return out


def main(argv: list[str]) -> None:
    import json
    print(json.dumps(assess(" ".join(argv[1:])), indent=1))


if __name__ == "__main__":
    import sys
    main(sys.argv)
