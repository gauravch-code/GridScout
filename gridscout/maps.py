"""Interactive evidence map; visual simplification never affects distance features."""
import html

import folium


def score_color(score):
    # Muted blue → turquoise → warm yellow.
    if score < .5:
        a,b,t = (87,127,157),(73,202,173),score*2
    else:
        a,b,t = (73,202,173),(245,214,103),(score-.5)*2
    return "#" + "".join(f"{int(x+(y-x)*t):02x}" for x,y in zip(a,b))


def build_map(top, lines, plants, counties, selected=None, show_lines=True, show_plants=True):
    map_view = folium.Map(location=[31.3,-99.4],zoom_start=6,tiles="OpenStreetMap",control_scale=True,prefer_canvas=True)
    map_view.get_root().header.add_child(folium.Element("<style>.leaflet-tile-pane{filter:grayscale(1) invert(1) brightness(.85)}.leaflet-container{background:#17242d}</style>"))
    west,south,east,north = counties.to_crs(4326).total_bounds
    map_view.fit_bounds([[south,west],[north,east]],padding=(12,12))
    borders = counties[["name","geometry"]].copy()
    borders.geometry = borders.geometry.simplify(700,preserve_topology=True)
    folium.GeoJson(borders.to_crs(4326).__geo_interface__,name="Texas counties",style_function=lambda _: {"color":"#8497aa","weight":.6,"fillOpacity":0,"opacity":.25}).add_to(map_view)
    if show_lines:
        visible = lines.loc[lines.voltage_kv >= 115,["line_id","voltage_kv","geometry"]].copy()
        visible.geometry = visible.geometry.simplify(150,preserve_topology=True)
        folium.GeoJson(visible.to_crs(4326).__geo_interface__,name="Transmission ≥115 kV",style_function=lambda _: {"color":"#9b8fc8","weight":1.2,"opacity":.45},tooltip=folium.GeoJsonTooltip(fields=["line_id","voltage_kv"],aliases=["Line","kV"])).add_to(map_view)
    if show_plants:
        layer = folium.FeatureGroup(name="Operating power plants")
        for _, plant in plants.to_crs(4326).iterrows():
            color = "#f1b964" if plant.solar_mw > 0 else "#67b8d5" if plant.wind_mw > 0 else "#79818b"
            folium.CircleMarker([plant.geometry.y,plant.geometry.x],radius=2.7,weight=0,fill=True,fill_color=color,fill_opacity=.65,tooltip=f"{html.escape(str(plant['name']))} · {html.escape(str(plant['type']))} · {plant.capacity_mw:,.0f} MW").add_to(layer)
        layer.add_to(map_view)
    prospects = folium.FeatureGroup(name="Top 50 prospects")
    for _, site in top.iterrows():
        is_selected = site.site_id == selected
        folium.CircleMarker([site.latitude,site.longitude],radius=10 if is_selected else 6,color="#ffffff" if is_selected else score_color(site.score),weight=2 if is_selected else 1,fill=True,fill_color=score_color(site.score),fill_opacity=.95,tooltip=site.site_id,popup=f"#{site['rank']} · {site.site_id}<br>Score {site.score:.3f}<br>{html.escape(str(site['county']))}<br>{site.distance_to_hv_m/1000:.1f} km to {site.voltage_kv:.0f} kV<br>{site.renewable_capacity_mw:,.0f} MW nearby").add_to(prospects)
    prospects.add_to(map_view)
    folium.LayerControl(collapsed=True).add_to(map_view)
    return map_view
