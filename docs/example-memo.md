### TX-379-1448-5000 — Converging infrastructure signals

Screening point in Wharton, at 29.2359, -95.9042. Weighted opportunity score: 0.915 (rank 1).

Writer: Deterministic evidence brief (no LLM)

Summary fields: `features.site_id, features.county, features.latitude, features.longitude, features.score, features.rank, sources.counties`

#### Why it looks promising

- The screening point is 0.31 km from mapped high-voltage line 307442. Proximity contributes +0.395 to the score. Sources: `features.distance_to_hv_m, features.line_id, features.contribution_transmission_distance, sources.transmission`
- Nearby operating solar and wind generators total 2,336.0 MW of nameplate capacity, contributing +0.250. This is a geographic co-location signal. Sources: `features.renewable_capacity_mw, features.contribution_renewable_capacity, nearby_plants, sources.plants`
- There are 12 unique operating renewable plants within 25 km (10 solar and 2 wind plant counts; hybrid plants can appear in both). This contributes +0.150. Sources: `features.renewable_count, features.solar_count, features.wind_count, features.radius_m, features.contribution_renewable_count, nearby_plants, sources.plants`
- The nearest qualifying line is recorded at 345 kV. Voltage contributes +0.119; it does not establish available capacity. Sources: `features.voltage_kv, features.contribution_voltage, nearest_line, sources.transmission`

#### Risks & unknowns

- Available interconnection capacity, upgrade costs, and queue position are unknown. Proximity to a line does not establish grid access. Sources: `risk_catalog.interconnection`
- Land ownership, parcel availability, access, and buildable acreage have not been assessed. Sources: `risk_catalog.land`
- Local permitting requirements and approval timelines have not been assessed. Sources: `risk_catalog.permitting`
- Flood exposure and other environmental constraints have not been assessed. Sources: `risk_catalog.flood`
- Congestion, nodal prices, curtailment, and storage revenue have not been modeled. Renewable nameplate MW is not a measurement of surplus generation. Sources: `risk_catalog.economics`
- Transmission vintage and line-level source dates may be old; current topology must be verified. EIA capacity is an annual snapshot. Sources: `risk_catalog.vintage`
- A screening cell and its representative point are not a developable parcel or a proposed interconnection location. Sources: `risk_catalog.resolution`

#### Check next

- Check the relevant transmission provider and interconnection queue; confirm a feasible point of interconnection, study requirements, and potential network upgrades. Sources: `check_catalog.interconnection`
- Cross-check the mapped line, voltage, service status, and nearby operating plants against current provider records. Sources: `check_catalog.vintage`
- Identify parcels and owners, verify access and easements, and assess usable acreage with a land professional. Sources: `check_catalog.land`
- Identify the local permitting authority and confirm applicable planning, fire-safety, and environmental requirements. Sources: `check_catalog.permitting`
- Screen FEMA flood maps and environmental constraints before selecting parcels. Sources: `check_catalog.flood`
- Evaluate nodal price history, congestion and renewable generation profiles, then model battery revenues and costs. Sources: `check_catalog.economics`

