"""Household-level cooling recommendation rules engine.

Deliberately *not* an LLM. Rules are auditable and traceable. Each rule fires
based on inputs from the dashboard's household questionnaire and the area
risk profile. Order matters — later rules override earlier ones for the
same intervention slot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Tier = Literal["Low", "Medium", "High", "Severe"]


@dataclass
class HouseholdInput:
    property_type: str       # "flat", "terraced", "semi", "detached"
    floor: str               # "ground", "mid", "top"
    epc_band: str            # "A".."G"
    tenure: str              # "owned", "private_rented", "social_rented"
    orientation: str         # "north", "south", "east", "west", "unknown"
    has_ac: bool
    area_risk_tier: Tier
    area_carbon_intensity: str  # "very low", "low", "moderate", "high", "very high"


@dataclass
class Recommendation:
    headline: str
    actions: list[str]
    avoid: list[str]
    carbon_note: str
    rationale: list[str]


PASSIVE = [
    "External shading (awnings, shutters, blinds outside the glass)",
    "Internal reflective blinds on south- and west-facing windows",
    "Night-purge ventilation — open windows when outdoor temp drops below indoor temp",
    "Light-coloured curtains; close them during the hottest part of the day",
]

VENTILATION = [
    "Cross-ventilation when secure (windows on opposite sides of the home)",
    "MEV / MVHR if you're retrofitting — boosts air change without losing security",
    "Ceiling or pedestal fans — 1/30th the power of AC for similar perceived cooling",
]

ACTIVE = [
    "Air-to-air heat pump (split AC) — cools in summer, heats in winter",
    "Portable AC only for short heatwave alerts — high energy cost",
    "If on social tenancy, raise overheating with landlord (Decent Homes 2025 standards)",
]


def recommend(h: HouseholdInput) -> Recommendation:
    actions: list[str] = []
    avoid: list[str] = []
    rationale: list[str] = []

    # Always start with passive measures
    actions.extend(PASSIVE[:2])

    # Top-floor flat = highest single-home risk driver
    if h.property_type == "flat" and h.floor == "top":
        rationale.append(
            "Top-floor flats heat from above (roof) and below (rising warm air). "
            "Passive measures alone often cannot keep indoor temperature under 26°C in heatwaves."
        )
        actions.append(PASSIVE[2])  # night purge
        actions.append(VENTILATION[2])  # fans
        if h.area_risk_tier in ("High", "Severe"):
            actions.append(ACTIVE[0])  # split AC

    # South or west-facing rooms get strong solar gain
    if h.orientation in ("south", "west"):
        rationale.append(
            f"{h.orientation.title()}-facing windows receive the most direct sun in afternoon — "
            "external shading is the highest-leverage intervention."
        )
        actions.append(PASSIVE[0])

    # Poor EPC = badly insulated *and* often poor ventilation
    if h.epc_band in ("E", "F", "G"):
        rationale.append(
            f"EPC band {h.epc_band} typically means poor insulation and limited ventilation control."
        )
        actions.append("Prioritise retrofit (insulation + controlled ventilation) before active cooling.")
        avoid.append("Avoid installing AC without addressing insulation first — you'll spend more for less effect.")

    # Renters have less control
    if h.tenure in ("private_rented", "social_rented"):
        rationale.append(
            "As a renter, prioritise interventions that don't require landlord consent — "
            "internal blinds, portable fans, night ventilation."
        )
        avoid.append("Fixed AC / heat-pump installations need landlord agreement.")

    # If they already have AC
    if h.has_ac:
        rationale.append("You already have AC — focus on reducing run-time, not capacity.")
        actions.append(
            "Use AC only when outdoor temp is above 28°C; set to 24–26°C, not lower. "
            "Combine with passive measures to reduce duty cycle."
        )

    # Severe area risk + no AC + high-risk dwelling
    if h.area_risk_tier == "Severe" and not h.has_ac and h.property_type == "flat":
        actions.append(ACTIVE[0])
        rationale.append(
            "Your area is in the Severe overheating tier and your property type is among the most heat-vulnerable. "
            "An air-to-air heat pump is the lowest-carbon active cooling option and doubles as winter heating."
        )

    # De-duplicate while preserving order
    seen = set()
    actions = [a for a in actions if not (a in seen or seen.add(a))]

    # Carbon framing
    ci = h.area_carbon_intensity.lower()
    if ci in ("very low", "low"):
        carbon_note = (
            f"Grid carbon is currently {ci} in your region — if you run AC, this is one of the better times."
        )
    elif ci == "moderate":
        carbon_note = "Grid carbon is moderate — try to shift heavy cooling load to lower-carbon hours where possible."
    else:
        carbon_note = (
            f"Grid carbon is {ci} — AC use has high embedded emissions. Lean on passive and ventilation measures."
        )

    # Headline
    if h.area_risk_tier == "Severe":
        headline = "Severe overheating risk — active cooling likely needed alongside passive measures."
    elif h.area_risk_tier == "High":
        headline = "High risk — passive + ventilation first; consider active cooling for heatwave days."
    elif h.area_risk_tier == "Medium":
        headline = "Medium risk — passive cooling measures should keep your home liveable in most summers."
    else:
        headline = "Low risk — simple passive and ventilation measures will be sufficient."

    return Recommendation(headline, actions, avoid, carbon_note, rationale)


if __name__ == "__main__":
    example = HouseholdInput(
        property_type="flat", floor="top", epc_band="C", tenure="private_rented",
        orientation="south", has_ac=False,
        area_risk_tier="Severe", area_carbon_intensity="low",
    )
    rec = recommend(example)
    print(rec.headline)
    print("\nActions:")
    for a in rec.actions:
        print(f"  - {a}")
    print("\nAvoid:")
    for a in rec.avoid:
        print(f"  - {a}")
    print("\nCarbon:", rec.carbon_note)
    print("\nWhy:")
    for r in rec.rationale:
        print(f"  - {r}")
