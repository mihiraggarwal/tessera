# import streamlit as st
# import streamlit.components.v1 as components
# import folium
# import numpy as np
# import pandas as pd
# from scipy.spatial import Voronoi
# from shapely.geometry import Polygon
# from streamlit_folium import st_folium
# from geopy.distance import geodesic
# import random
# import math

# st.set_page_config(layout="wide", page_title="India Health Voronoi Locator")
# st.title("Voronoi-based Health Facility Locator")

# # -------------------------------------------------------------------
# # Session state for persistent scenario
# # -------------------------------------------------------------------
# if "scenario" not in st.session_state:
#     st.session_state["scenario"] = None  # "add", "remove", "move", or None


# def set_scenario_add():
#     st.session_state["scenario"] = "add"


# def set_scenario_remove():
#     st.session_state["scenario"] = "remove"


# def set_scenario_move():
#     st.session_state["scenario"] = "move"


# def clear_scenario():
#     st.session_state["scenario"] = None


# # -------------------------------------------------------------------
# # Data loading
# # -------------------------------------------------------------------
# @st.cache_data
# def load_facilities():
#     # Read everything as string to avoid mixed-type warnings
#     df = pd.read_csv(
#         "geocode_health_centre.csv",
#         dtype=str,
#         low_memory=False,
#     )

#     df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
#     df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
#     df = df[df["Latitude"].between(-90, 90) & df["Longitude"].between(-180, 180)]

#     df["name"] = (
#         df["Facility Name"].astype(str)
#         + " ("
#         + df["Facility Type"].astype(str)
#         + ", "
#         + df["District Name"].astype(str)
#         + ")"
#     )

#     coords = df[["Longitude", "Latitude"]].to_numpy()
#     names = df["name"].tolist()
#     return df, coords, names


# def voronoi_polygons(vor_obj):
#     polys = []
#     for i, region_index in enumerate(vor_obj.point_region):
#         vert_idx = vor_obj.regions[region_index]
#         if -1 in vert_idx or len(vert_idx) == 0:
#             continue
#         poly_coords = vor_obj.vertices[vert_idx]
#         polys.append((i, Polygon(poly_coords)))
#     return polys


# # --- MEC helpers (Euclidean on lon/lat) ---
# def _dist(a, b):
#     return math.hypot(a[0] - b[0], a[1] - b[1])


# def _circle_two_points(p, q):
#     cx = (p[0] + q[0]) / 2.0
#     cy = (p[1] + q[1]) / 2.0
#     r = _dist(p, q) / 2.0
#     return (cx, cy), r


# def _circle_three_points(a, b, c):
#     d = 2 * (
#         a[0] * (b[1] - c[1])
#         + b[0] * (c[1] - a[1])
#         + c[0] * (a[1] - b[1])
#     )
#     if abs(d) < 1e-12:
#         circles = []
#         for p, q in ((a, b), (a, c), (b, c)):
#             circles.append(_circle_two_points(p, q))
#         best = circles[0]
#         for center, r in circles:
#             if all(_dist(center, p) <= r + 1e-9 for p in (a, b, c)) and r < best[1]:
#                 best = (center, r)
#         return best
#     ux = (
#         (a[0] ** 2 + a[1] ** 2) * (b[1] - c[1])
#         + (b[0] ** 2 + b[1] ** 2) * (c[1] - a[1])
#         + (c[0] ** 2 + c[1] ** 2) * (a[1] - b[1])
#     ) / d
#     uy = (
#         (a[0] ** 2 + a[1] ** 2) * (c[0] - b[0])
#         + (b[0] ** 2 + b[1] ** 2) * (a[0] - c[0])
#         + (c[0] ** 2 + c[1] ** 2) * (b[0] - a[0])
#     ) / d
#     center = (ux, uy)
#     r = max(_dist(center, a), _dist(center, b), _dist(center, c))
#     return center, r


# def _is_in_circle(p, center, r):
#     return _dist(p, center) <= r + 1e-9


# def minimum_enclosing_circle(points):
#     pts = [(float(x), float(y)) for x, y in points]
#     if not pts:
#         return (0.0, 0.0), 0.0
#     random.shuffle(pts)
#     center = pts[0]
#     r = 0.0
#     for i, p in enumerate(pts[1:], start=1):
#         if not _is_in_circle(p, center, r):
#             center = p
#             r = 0.0
#             for j in range(i):
#                 q = pts[j]
#                 if not _is_in_circle(q, center, r):
#                     center, r = _circle_two_points(p, q)
#                     for k in range(j):
#                         rp = pts[k]
#                         if not _is_in_circle(rp, center, r):
#                             center, r = _circle_three_points(p, q, rp)
#     return center, r


# # ---------- CACHED HEAVY STUFF ----------
# @st.cache_data
# def compute_voronoi_cached(coords_key):
#     coords = np.array(coords_key)
#     vor = Voronoi(coords)
#     polys = voronoi_polygons(vor)

#     # largest cell by area
#     largest_idx = None
#     largest_area = 0.0
#     largest_centroid = None
#     for i, poly in polys:
#         a = poly.area
#         if a > largest_area:
#             largest_area = a
#             largest_idx = i
#             largest_centroid = poly.centroid
#     return polys, largest_idx, largest_centroid


# @st.cache_data
# def compute_mec_cached(coords_key):
#     coords = np.array(coords_key)
#     if len(coords) < 2:
#         return None, 0.0
#     center, _ = minimum_enclosing_circle(coords)
#     lon_c, lat_c = center
#     radius_km = 0.0
#     for x, y in coords:
#         d = geodesic((lat_c, lon_c), (y, x)).km
#         if d > radius_km:
#             radius_km = d
#     return (lon_c, lat_c), radius_km


# # =============================================================================
# #  MAIN APP
# # =============================================================================

# df_fac, all_coords, all_names = load_facilities()

# # ----------------------------
# # 1. Sidebar: scope & options
# # ----------------------------

# analysis_mode = st.sidebar.radio(
#     "Data scope",
#     ["All India", "Single-state analysis"],
#     index=0,
# )

# selected_state = None
# state_bbox = None

# if analysis_mode == "Single-state analysis":
#     state_options = sorted(df_fac["State Name"].dropna().unique())
#     selected_state = st.sidebar.selectbox("State for analysis", state_options)
#     df_current = df_fac[df_fac["State Name"] == selected_state].copy()
#     if df_current.empty:
#         st.error("No facilities found for the selected state.")
#         st.stop()
#     min_lat = df_current["Latitude"].min()
#     max_lat = df_current["Latitude"].max()
#     min_lon = df_current["Longitude"].min()
#     max_lon = df_current["Longitude"].max()
#     state_bbox = [[min_lat, min_lon], [max_lat, max_lon]]
# else:
#     df_current = df_fac.copy()

# coords_all = df_current[["Longitude", "Latitude"]].to_numpy()
# names_all = df_current["name"].tolist()
# n_total = len(coords_all)

# if n_total == 0:
#     st.error("No facilities available in current scope.")
#     st.stop()

# show_voronoi = st.sidebar.checkbox("Show Voronoi polygons", value=True)
# show_mec = st.sidebar.checkbox("Show minimum enclosing circle (MEC)", value=False)

# st.sidebar.write(f"Facilities in scope: {n_total}")

# # Sampling behaviour
# if n_total <= 300:
#     sample_size = n_total
#     st.sidebar.write(f"Sample size for Voronoi: using all {n_total} facilities (no subsampling)")
# else:
#     max_sample = min(2000, n_total)
#     default_sample = min(800, max_sample)
#     sample_size = st.sidebar.slider(
#         "Sample size for Voronoi (higher = slower but more detail)",
#         min_value=100,
#         max_value=int(max_sample),
#         value=int(default_sample),
#         step=50,
#     )

# # ----------------------------
# # 2. Sample points (deterministic)
# # ----------------------------

# if sample_size == n_total:
#     sample_idx = np.arange(n_total)
# else:
#     rng = np.random.default_rng(42)
#     sample_idx = rng.choice(n_total, size=sample_size, replace=False)

# coords_sample = coords_all[sample_idx]
# names_sample = [names_all[i] for i in sample_idx]

# st.sidebar.write(f"Sampled for Voronoi: {sample_size}")

# coords_key = tuple(map(tuple, coords_sample))

# # ----------------------------
# # 3. Use cached Voronoi / MEC
# # ----------------------------

# vor_polys = []
# largest_cell_idx = None
# largest_cell_centroid = None

# if show_voronoi and sample_size >= 4:
#     vor_polys, largest_cell_idx, largest_cell_centroid = compute_voronoi_cached(coords_key)
#     if largest_cell_idx is not None:
#         st.sidebar.markdown(
#             f"**Largest Voronoi cell (sampled)**: {names_sample[largest_cell_idx]}"
#         )

# mec_center = None
# mec_radius_km = 0.0
# if show_mec and sample_size >= 2:
#     mec_center, mec_radius_km = compute_mec_cached(coords_key)
#     if mec_center is not None:
#         st.sidebar.markdown(
#             f"**MEC radius (sampled)**: ~{mec_radius_km:.1f} km"
#         )


# # ----------------------------
# # 4. Nearest-facility (sampled)
# # ----------------------------

# def nearest_facility(qx, qy):
#     dists = [geodesic((qy, qx), (y, x)).km for (x, y) in coords_sample]
#     idx = int(np.argmin(dists))
#     return idx, dists[idx]


# # ----------------------------
# # 5. Layout
# # ----------------------------

# col1, col2 = st.columns(2)
# click = None

# # ---------- LEFT: base map ----------
# with col1:
#     st.subheader("Base Map (Click anywhere)")

#     # Map center
#     if state_bbox is not None:
#         center_lat = (state_bbox[0][0] + state_bbox[1][0]) / 2.0
#         center_lon = (state_bbox[0][1] + state_bbox[1][1]) / 2.0
#         zoom_start = 6
#     else:
#         center_lat, center_lon = 20.5937, 78.9629
#         zoom_start = 5

#     m = folium.Map(
#         location=[center_lat, center_lon],
#         zoom_start=zoom_start,
#         tiles="cartodbpositron",
#     )

#     # Sampled facility markers
#     for (x, y), name in zip(coords_sample, names_sample):
#         folium.CircleMarker(
#             [y, x],
#             radius=3,
#             tooltip=name,
#             color="red",
#             fill=True,
#             fill_opacity=0.9,
#         ).add_to(m)

#     # Optional bounding box for state
#     if state_bbox is not None:
#         folium.Rectangle(
#             bounds=state_bbox,
#             color="blue",
#             weight=2,
#             fill=False,
#             dash_array="5, 5",
#             tooltip=f"{selected_state} (approx. bounding box)",
#         ).add_to(m)

#     st.markdown(
#         "1. Click anywhere on this map to pick a location.\n"
#         "2. On the right, choose a scenario button to visualise planning actions."
#     )

#     map_data = st_folium(m, width=700, height=700, key="base_map")
#     if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
#         click = map_data["last_clicked"]

# # ---------- RIGHT: polygons map (STATIC IN BROWSER) ----------
# with col2:
#     st.subheader("Voronoi map, nearest facility & scenarios")

#     scenario = st.session_state["scenario"]

#     nearest_idx = None
#     nearest_name = None
#     d_km = None
#     nx = ny = None
#     row = None
#     qx = qy = None

#     if click:
#         qx = float(click["lng"])
#         qy = float(click["lat"])
#         nearest_idx, d_km = nearest_facility(qx, qy)
#         nearest_name = names_sample[nearest_idx]
#         nx, ny = coords_sample[nearest_idx]
#         row = df_current.iloc[sample_idx[nearest_idx]]

#         st.success(
#             f"Nearest facility: {nearest_name}\n\n"
#             f"- Distance ≈ {d_km:.1f} km\n"
#             f"- Facility Type: {row['Facility Type']}\n"
#             f"- State: {row['State Name']}\n"
#             f"- District: {row['District Name']}"
#         )
#     else:
#         st.info("Click on the left map to select a location.")

#     # Center of polygons map (view map only)
#     if state_bbox is not None:
#         map_center = [
#             (state_bbox[0][0] + state_bbox[1][0]) / 2.0,
#             (state_bbox[0][1] + state_bbox[1][1]) / 2.0,
#         ]
#         zoom2 = 6
#     else:
#         map_center = [20.5937, 78.9629]
#         zoom2 = 5

#     # Build folium map for polygons (no callbacks)
#     m2 = folium.Map(
#         location=map_center,
#         zoom_start=zoom2,
#         tiles="cartodbpositron",
#     )

#     # Voronoi polygons
#     if show_voronoi and vor_polys:
#         colors = ["#%06x" % np.random.randint(0, 0xFFFFFF) for _ in vor_polys]
#         for (i, poly), color in zip(vor_polys, colors):
#             lonlat = np.array(poly.exterior.coords)
#             is_largest = (i == largest_cell_idx)
#             folium.Polygon(
#                 locations=[[lat, lon] for lon, lat in lonlat],
#                 color="yellow" if is_largest else "black",
#                 weight=3 if is_largest else 1,
#                 fill=True,
#                 fill_color=color,
#                 fill_opacity=0.2,
#                 tooltip=names_sample[i],
#             ).add_to(m2)

#     # Facilities (highlight nearest if clicked)
#     for idx_pt, ((x, y), name) in enumerate(zip(coords_sample, names_sample)):
#         color = "green" if (nearest_idx is not None and idx_pt == nearest_idx) else "red"
#         folium.CircleMarker(
#             [y, x],
#             radius=3,
#             tooltip=name,
#             color=color,
#             fill=True,
#             fill_opacity=0.9,
#         ).add_to(m2)

#     # Click marker + line
#     if click and nearest_idx is not None:
#         folium.Marker(
#             [qy, qx], tooltip="Clicked location", icon=folium.Icon(color="blue")
#         ).add_to(m2)
#         folium.PolyLine([[qy, qx], [ny, nx]], color="green", weight=3).add_to(m2)

#     # Bounding box + MEC overlays
#     if state_bbox is not None:
#         folium.Rectangle(
#             bounds=state_bbox,
#             color="blue",
#             weight=2,
#             fill=False,
#             dash_array="5, 5",
#             tooltip=f"{selected_state} (approx. bounding box)",
#         ).add_to(m2)

#     if show_mec and mec_center is not None and mec_radius_km > 0:
#         lon_c, lat_c = mec_center
#         folium.Circle(
#             location=[lat_c, lon_c],
#             radius=mec_radius_km * 1000.0,
#             color="purple",
#             fill=False,
#             weight=2,
#             tooltip="Approx. minimum enclosing circle (sampled)",
#         ).add_to(m2)

#     # ------------------------------------------------------
#     # Scenario overlays ON THE MAIN MAP (add/remove/move)
#     # ------------------------------------------------------
#     if click and nearest_idx is not None and nx is not None and ny is not None:
#         if scenario == "add":
#             # Candidate facility at click
#             folium.Marker(
#                 [qy, qx],
#                 tooltip="Candidate facility (new)",
#                 icon=folium.Icon(color="purple", icon="plus"),
#             ).add_to(m2)

#             # Emphasise existing nearest
#             folium.Marker(
#                 [ny, nx],
#                 tooltip=f"Existing nearest: {nearest_name}",
#                 icon=folium.Icon(color="green"),
#             ).add_to(m2)

#             folium.PolyLine([[qy, qx], [ny, nx]], color="purple", weight=3).add_to(m2)

#         elif scenario == "remove":
#             # Find 2nd-nearest facility
#             second_idx = None
#             second_dist = None
#             for j, (x, y) in enumerate(coords_sample):
#                 if j == nearest_idx:
#                     continue
#                 d = geodesic((qy, qx), (y, x)).km
#                 if second_dist is None or d < second_dist:
#                     second_dist = d
#                     second_idx = j

#             if second_idx is not None:
#                 second_name = names_sample[second_idx]
#                 sx, sy = coords_sample[second_idx]

#                 # Mark removed nearest facility
#                 folium.Marker(
#                     [ny, nx],
#                     tooltip=f"Removed facility: {nearest_name}",
#                     icon=folium.Icon(color="red"),
#                 ).add_to(m2)

#                 # Mark new nearest
#                 folium.Marker(
#                     [sy, sx],
#                     tooltip=f"New nearest: {second_name}",
#                     icon=folium.Icon(color="green"),
#                 ).add_to(m2)

#                 folium.PolyLine([[qy, qx], [sy, sx]], color="orange", weight=3).add_to(m2)

#         elif scenario == "move":
#             # Show original location and moved location
#             folium.Marker(
#                 [ny, nx],
#                 tooltip=f"Original location of {nearest_name}",
#                 icon=folium.Icon(color="green"),
#             ).add_to(m2)

#             folium.Marker(
#                 [qy, qx],
#                 tooltip=f"New location of {nearest_name}",
#                 icon=folium.Icon(color="purple", icon="arrow-up"),
#             ).add_to(m2)

#             folium.PolyLine([[qy, qx], [ny, nx]], color="purple", weight=3).add_to(m2)

#     # Render static HTML map so dragging/zooming doesn't trigger reruns
#     map_html = m2.get_root().render()
#     components.html(map_html, height=500)

#     # ---------- Scenario buttons ----------
#     st.markdown("### Scenario actions")

#     if not click:
#         st.caption("Click on the left map first to enable scenario actions.")
#     else:
#         st.caption(
#             "Use these buttons to overlay planning scenarios on the Voronoi map. "
#             "The scenario stays active until you press **Clear scenario**."
#         )

#     c1, c2, c3, c4 = st.columns(4)
#     with c1:
#         st.button("Add facility here", key="btn_add", on_click=set_scenario_add, disabled=not bool(click))
#     with c2:
#         st.button("Remove nearest", key="btn_remove", on_click=set_scenario_remove, disabled=not bool(click))
#     with c3:
#         st.button("Move nearest here", key="btn_move", on_click=set_scenario_move, disabled=not bool(click))
#     with c4:
#         st.button("Clear scenario", key="btn_clear", on_click=clear_scenario)

#     # ---------- Scenario text explanations ----------
#     if click and nearest_idx is not None and scenario in {"add", "remove", "move"}:
#         if scenario == "add":
#             st.markdown("#### Scenario: Add a new facility at this point")
#             base_dist = d_km
#             st.write(
#                 f"- Current nearest facility: **{nearest_name}** at ≈ **{base_dist:.1f} km**."
#             )
#             cand_dists = [geodesic((qy, qx), (y, x)).km for (x, y) in coords_sample]
#             base_dists = [geodesic((y, x), (ny, nx)).km for (x, y) in coords_sample]
#             improved = sum(1 for cd, bd in zip(cand_dists, base_dists) if cd < bd)
#             st.write(
#                 f"- Among the **{len(coords_sample)}** sampled locations, "
#                 f"**{improved}** would be closer to this new facility than to **{nearest_name}**."
#             )

#         elif scenario == "remove":
#             st.markdown("#### Scenario: Remove the current nearest facility")
#             # Find second nearest again for text
#             second_idx = None
#             second_dist = None
#             for j, (x, y) in enumerate(coords_sample):
#                 if j == nearest_idx:
#                     continue
#                 d = geodesic((qy, qx), (y, x)).km
#                 if second_dist is None or d < second_dist:
#                     second_dist = d
#                     second_idx = j

#             if second_idx is not None:
#                 second_name = names_sample[second_idx]
#                 st.write(
#                     f"- If **{nearest_name}** is removed, the new nearest facility is "
#                     f"**{second_name}** at ≈ **{second_dist:.1f} km** "
#                     f"(increase of ≈ **{(second_dist - d_km):.1f} km**)."
#                 )
#             else:
#                 st.write("- No alternative facility found in the sampled set.")

#         elif scenario == "move":
#             st.markdown("#### Scenario: Move the nearest facility to this point")
#             st.write(
#                 f"- Currently, **{nearest_name}** is at ≈ **{d_km:.1f} km** from this point. "
#                 f"If moved here, that distance becomes **0 km**."
#             )
#             moved_dists = [geodesic((qy, qx), (y, x)).km for (x, y) in coords_sample]
#             old_dists = [geodesic((y, x), (ny, nx)).km for (x, y) in coords_sample]
#             improved = sum(1 for md, od in zip(moved_dists, old_dists) if md < od)
#             st.write(
#                 f"- Among the **{len(coords_sample)}** sampled locations, "
#                 f"**{improved}** would be closer to the moved facility at this point "
#                 f"than to its original location."
#             )

import streamlit as st
import streamlit.components.v1 as components
import folium
import numpy as np
import pandas as pd
from scipy.spatial import Voronoi, KDTree
from shapely.geometry import Polygon
from streamlit_folium import st_folium
from geopy.distance import geodesic
import random
import math

st.set_page_config(layout="wide", page_title="India Health Voronoi Locator")
st.title("Voronoi-based Health Facility Locator")

# -------------------------------------------------------------------
# Session state for persistent scenario
# -------------------------------------------------------------------
if "scenario" not in st.session_state:
    st.session_state["scenario"] = None  # "add", "remove", "move", or None


def set_scenario_add():
    st.session_state["scenario"] = "add"


def set_scenario_remove():
    st.session_state["scenario"] = "remove"


def set_scenario_move():
    st.session_state["scenario"] = "move"


def clear_scenario():
    st.session_state["scenario"] = None


# -------------------------------------------------------------------
# Data loading
# -------------------------------------------------------------------
@st.cache_data
def load_facilities():
    # Read everything as string to avoid mixed-type warnings
    df = pd.read_csv(
        "geocode_health_centre.csv",
        dtype=str,
        low_memory=False,
    )

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df = df[df["Latitude"].between(-90, 90) & df["Longitude"].between(-180, 180)]

    df["name"] = (
        df["Facility Name"].astype(str)
        + " ("
        + df["Facility Type"].astype(str)
        + ", "
        + df["District Name"].astype(str)
        + ")"
    )

    coords = df[["Longitude", "Latitude"]].to_numpy()
    names = df["name"].tolist()
    return df, coords, names


def voronoi_polygons(vor_obj):
    polys = []
    for i, region_index in enumerate(vor_obj.point_region):
        vert_idx = vor_obj.regions[region_index]
        if -1 in vert_idx or len(vert_idx) == 0:
            continue
        poly_coords = vor_obj.vertices[vert_idx]
        polys.append((i, Polygon(poly_coords)))
    return polys


# --- MEC helpers (Euclidean on lon/lat) ---
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _circle_two_points(p, q):
    cx = (p[0] + q[0]) / 2.0
    cy = (p[1] + q[1]) / 2.0
    r = _dist(p, q) / 2.0
    return (cx, cy), r


def _circle_three_points(a, b, c):
    d = 2 * (
        a[0] * (b[1] - c[1])
        + b[0] * (c[1] - a[1])
        + c[0] * (a[1] - b[1])
    )
    if abs(d) < 1e-12:
        circles = []
        for p, q in ((a, b), (a, c), (b, c)):
            circles.append(_circle_two_points(p, q))
        best = circles[0]
        for center, r in circles:
            if all(_dist(center, p) <= r + 1e-9 for p in (a, b, c)) and r < best[1]:
                best = (center, r)
        return best
    ux = (
        (a[0] ** 2 + a[1] ** 2) * (b[1] - c[1])
        + (b[0] ** 2 + b[1] ** 2) * (c[1] - a[1])
        + (c[0] ** 2 + c[1] ** 2) * (a[1] - b[1])
    ) / d
    uy = (
        (a[0] ** 2 + a[1] ** 2) * (c[0] - b[0])
        + (b[0] ** 2 + b[1] ** 2) * (a[0] - c[0])
        + (c[0] ** 2 + c[1] ** 2) * (b[0] - a[0])
    ) / d
    center = (ux, uy)
    r = max(_dist(center, a), _dist(center, b), _dist(center, c))
    return center, r


def _is_in_circle(p, center, r):
    return _dist(p, center) <= r + 1e-9


def minimum_enclosing_circle(points):
    pts = [(float(x), float(y)) for x, y in points]
    if not pts:
        return (0.0, 0.0), 0.0
    random.shuffle(pts)
    center = pts[0]
    r = 0.0
    for i, p in enumerate(pts[1:], start=1):
        if not _is_in_circle(p, center, r):
            center = p
            r = 0.0
            for j in range(i):
                q = pts[j]
                if not _is_in_circle(q, center, r):
                    center, r = _circle_two_points(p, q)
                    for k in range(j):
                        rp = pts[k]
                        if not _is_in_circle(rp, center, r):
                            center, r = _circle_three_points(p, q, rp)
    return center, r


# ---------- Outlier filtering ----------
def filter_outliers_by_nn(df, threshold_km: float):
    """
    Remove facilities whose nearest neighbour is farther than threshold_km.
    Uses an approximate flat projection (km) for speed.
    """
    if len(df) < 2 or threshold_km <= 0:
        return df

    lat = df["Latitude"].to_numpy(dtype=float)
    lon = df["Longitude"].to_numpy(dtype=float)

    lat0 = float(np.nanmean(lat))
    x_scale = 111.320 * np.cos(np.deg2rad(lat0))  # km per degree lon
    y_scale = 110.574                              # km per degree lat

    xs = lon * x_scale
    ys = lat * y_scale
    pts = np.column_stack([xs, ys])

    tree = KDTree(pts)
    dists, _ = tree.query(pts, k=2)
    nn_dists = dists[:, 1]  # distance to nearest other point, in km

    mask = nn_dists <= threshold_km
    return df.loc[mask].copy()


# ---------- CACHED HEAVY STUFF ----------
@st.cache_data
def compute_voronoi_cached(coords_key):
    coords = np.array(coords_key)
    vor = Voronoi(coords)
    polys = voronoi_polygons(vor)

    # largest cell by area
    largest_idx = None
    largest_area = 0.0
    largest_centroid = None
    for i, poly in polys:
        a = poly.area
        if a > largest_area:
            largest_area = a
            largest_idx = i
            largest_centroid = poly.centroid
    return polys, largest_idx, largest_centroid


@st.cache_data
def compute_mec_cached(coords_key):
    coords = np.array(coords_key)
    if len(coords) < 2:
        return None, 0.0
    center, _ = minimum_enclosing_circle(coords)
    lon_c, lat_c = center
    radius_km = 0.0
    for x, y in coords:
        d = geodesic((lat_c, lon_c), (y, x)).km
        if d > radius_km:
            radius_km = d
    return (lon_c, lat_c), radius_km


# =============================================================================
#  MAIN APP
# =============================================================================

df_fac, _, _ = load_facilities()

# ----------------------------
# 1. Sidebar: scope & options
# ----------------------------

analysis_mode = st.sidebar.radio(
    "Data scope",
    ["All India", "Single-state analysis"],
    index=0,
)

selected_state = None
state_bbox = None

if analysis_mode == "Single-state analysis":
    state_options = sorted(df_fac["State Name"].dropna().unique())
    selected_state = st.sidebar.selectbox("State for analysis", state_options)

show_voronoi = st.sidebar.checkbox("Show Voronoi polygons", value=True)
show_mec = st.sidebar.checkbox("Show minimum enclosing circle (MEC)", value=False)

# Outlier sanity-check slider
outlier_threshold_km = st.sidebar.slider(
    "Outlier filter: drop facilities whose nearest neighbour is farther than (km)",
    min_value=0,
    max_value=500,
    value=0,           # 0 = off
    step=25,
)

# ----------------------------
# 2. Choose data in scope & apply outlier filter
# ----------------------------

if analysis_mode == "Single-state analysis":
    df_current = df_fac[df_fac["State Name"] == selected_state].copy()
    if df_current.empty:
        st.error("No facilities found for the selected state.")
        st.stop()

    before = len(df_current)
    df_current = filter_outliers_by_nn(df_current, outlier_threshold_km)
    after = len(df_current)
    removed = before - after

    if removed > 0 and outlier_threshold_km > 0:
        st.sidebar.write(
            f"Outlier filter removed {removed} isolated facility(ies) "
            f"from {selected_state} (> {outlier_threshold_km} km from any neighbour)."
        )

    if after == 0:
        st.error(
            "All facilities in this state were removed by the outlier filter. "
            "Reduce the distance threshold or disable the filter."
        )
        st.stop()

    # Bounding box based on cleaned facilities
    min_lat = df_current["Latitude"].min()
    max_lat = df_current["Latitude"].max()
    min_lon = df_current["Longitude"].min()
    max_lon = df_current["Longitude"].max()
    state_bbox = [[min_lat, min_lon], [max_lat, max_lon]]
else:
    before = len(df_fac)
    df_current = filter_outliers_by_nn(df_fac.copy(), outlier_threshold_km)
    after = len(df_current)
    removed = before - after
    if removed > 0 and outlier_threshold_km > 0:
        st.sidebar.write(
            f"Outlier filter removed {removed} isolated facility(ies) "
            f"across India (> {outlier_threshold_km} km from any neighbour)."
        )

df_current = df_current.reset_index(drop=True)

coords_all = df_current[["Longitude", "Latitude"]].to_numpy()
names_all = df_current["name"].tolist()
n_total = len(coords_all)

if n_total == 0:
    st.error("No facilities available in current scope after filtering.")
    st.stop()

st.sidebar.write(f"Facilities in scope (after filtering): {n_total}")

# ----------------------------
# 3. Sampling behaviour
# ----------------------------

if n_total <= 300:
    sample_size = n_total
    st.sidebar.write(f"Sample size for Voronoi: using all {n_total} facilities (no subsampling)")
else:
    max_sample = min(2000, n_total)
    default_sample = min(800, max_sample)
    sample_size = st.sidebar.slider(
        "Sample size for Voronoi (higher = slower but more detail)",
        min_value=100,
        max_value=int(max_sample),
        value=int(default_sample),
        step=50,
    )

# ----------------------------
# 4. Sample points (deterministic)
# ----------------------------

if sample_size == n_total:
    sample_idx = np.arange(n_total)
else:
    rng = np.random.default_rng(42)
    sample_idx = rng.choice(n_total, size=sample_size, replace=False)

coords_sample = coords_all[sample_idx]
names_sample = [names_all[i] for i in sample_idx]

st.sidebar.write(f"Sampled for Voronoi: {sample_size}")

base_coords_key = tuple(map(tuple, coords_sample))

# ----------------------------
# 5. Base Voronoi / MEC
# ----------------------------

base_vor_polys = []
base_largest_cell_idx = None
base_largest_cell_centroid = None

if show_voronoi and sample_size >= 4:
    base_vor_polys, base_largest_cell_idx, base_largest_cell_centroid = compute_voronoi_cached(
        base_coords_key
    )

mec_center = None
mec_radius_km = 0.0
if show_mec and sample_size >= 2:
    mec_center, mec_radius_km = compute_mec_cached(base_coords_key)
    if mec_center is not None:
        st.sidebar.markdown(
            f"**MEC radius (sampled)**: ~{mec_radius_km:.1f} km"
        )


# ----------------------------
# 6. Nearest-facility (sampled)
# ----------------------------

def nearest_facility(qx, qy):
    dists = [geodesic((qy, qx), (y, x)).km for (x, y) in coords_sample]
    idx = int(np.argmin(dists))
    return idx, dists[idx]


# ----------------------------
# 7. Layout
# ----------------------------

col1, col2 = st.columns(2)
click = None

# ---------- LEFT: base map ----------
with col1:
    st.subheader("Base Map (Click anywhere)")

    # Map center
    if state_bbox is not None:
        center_lat = (state_bbox[0][0] + state_bbox[1][0]) / 2.0
        center_lon = (state_bbox[0][1] + state_bbox[1][1]) / 2.0
        zoom_start = 6
    else:
        center_lat, center_lon = 20.5937, 78.9629
        zoom_start = 5

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="cartodbpositron",
    )

    # Sampled facility markers
    for (x, y), name in zip(coords_sample, names_sample):
        folium.CircleMarker(
            [y, x],
            radius=3,
            tooltip=name,
            color="red",
            fill=True,
            fill_opacity=0.9,
        ).add_to(m)

    # Optional bounding box for state
    if state_bbox is not None:
        folium.Rectangle(
            bounds=state_bbox,
            color="blue",
            weight=2,
            fill=False,
            dash_array="5, 5",
            tooltip=f"{selected_state} (approx. bounding box)",
        ).add_to(m)

    st.markdown(
        "1. Click anywhere on this map to pick a location.\n"
        "2. On the right, choose a scenario button to visualise planning actions."
    )

    map_data = st_folium(m, width=700, height=700, key="base_map")
    if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
        click = map_data["last_clicked"]

# ---------- RIGHT: polygons map (STATIC IN BROWSER) ----------
with col2:
    st.subheader("Voronoi map, nearest facility & scenarios")

    scenario = st.session_state["scenario"]

    nearest_idx = None
    nearest_name = None
    d_km = None
    nx = ny = None
    row = None
    qx = qy = None

    if click:
        qx = float(click["lng"])
        qy = float(click["lat"])
        nearest_idx, d_km = nearest_facility(qx, qy)
        nearest_name = names_sample[nearest_idx]
        nx, ny = coords_sample[nearest_idx]
        row = df_current.iloc[sample_idx[nearest_idx]]

        st.success(
            f"Nearest facility: {nearest_name}\n\n"
            f"- Distance ≈ {d_km:.1f} km\n"
            f"- Facility Type: {row['Facility Type']}\n"
            f"- State: {row['State Name']}\n"
            f"- District: {row['District Name']}"
        )
    else:
        st.info("Click on the left map to select a location.")

    # ----------------------------
    # Scenario-adjusted facility set for Voronoi
    # ----------------------------
    scenario_active = (
        click is not None and nearest_idx is not None and scenario in {"add", "remove", "move"}
    )

    if scenario_active:
        scenario_coords = coords_sample.copy()
        scenario_names = list(names_sample)

        if scenario == "add":
            scenario_coords = np.vstack([scenario_coords, np.array([qx, qy])])
            scenario_names.append("New facility (candidate)")
        elif scenario == "remove":
            scenario_coords = np.delete(scenario_coords, nearest_idx, axis=0)
            scenario_names.pop(nearest_idx)
        elif scenario == "move":
            scenario_coords[nearest_idx] = [qx, qy]
    else:
        scenario_coords = coords_sample
        scenario_names = names_sample

    # Choose polygons to draw: base or scenario-adjusted
    if show_voronoi and len(scenario_coords) >= 4:
        scenario_coords_key = tuple(map(tuple, scenario_coords))
        polys_to_draw, highlight_idx, _ = compute_voronoi_cached(scenario_coords_key)
    else:
        polys_to_draw = []
        highlight_idx = None

    # Center of polygons map (view map only)
    if state_bbox is not None:
        map_center = [
            (state_bbox[0][0] + state_bbox[1][0]) / 2.0,
            (state_bbox[0][1] + state_bbox[1][1]) / 2.0,
        ]
        zoom2 = 6
    else:
        map_center = [20.5937, 78.9629]
        zoom2 = 5

    # Build folium map for polygons (no callbacks)
    m2 = folium.Map(
        location=map_center,
        zoom_start=zoom2,
        tiles="cartodbpositron",
    )

    # Voronoi polygons (from scenario-adjusted coords if any)
    if show_voronoi and polys_to_draw:
        colors = ["#%06x" % np.random.randint(0, 0xFFFFFF) for _ in polys_to_draw]
        for (i, poly), color in zip(polys_to_draw, colors):
            lonlat = np.array(poly.exterior.coords)
            is_highlight = (highlight_idx is not None and i == highlight_idx)
            folium.Polygon(
                locations=[[lat, lon] for lon, lat in lonlat],
                color="yellow" if is_highlight else "black",
                weight=3 if is_highlight else 1,
                fill=True,
                fill_color=color,
                fill_opacity=0.2,
                tooltip=scenario_names[i],
            ).add_to(m2)

    # Facility seed markers (match Voronoi seeds)
    for (x, y), name in zip(scenario_coords, scenario_names):
        folium.CircleMarker(
            [y, x],
            radius=3,
            tooltip=name,
            color="red",
            fill=True,
            fill_opacity=0.9,
        ).add_to(m2)

    # Click marker + base nearest line
    if click and nearest_idx is not None:
        folium.Marker(
            [qy, qx], tooltip="Clicked location", icon=folium.Icon(color="blue")
        ).add_to(m2)
        folium.PolyLine([[qy, qx], [ny, nx]], color="green", weight=3).add_to(m2)

    # Bounding box + MEC overlays
    if state_bbox is not None:
        folium.Rectangle(
            bounds=state_bbox,
            color="blue",
            weight=2,
            fill=False,
            dash_array="5, 5",
            tooltip=f"{selected_state} (approx. bounding box)",
        ).add_to(m2)

    if show_mec and mec_center is not None and mec_radius_km > 0:
        lon_c, lat_c = mec_center
        folium.Circle(
            location=[lat_c, lon_c],
            radius=mec_radius_km * 1000.0,
            color="purple",
            fill=False,
            weight=2,
            tooltip="Approx. minimum enclosing circle (sampled)",
        ).add_to(m2)

    # Scenario overlays ON THE MAIN MAP (add/remove/move)
    if click and nearest_idx is not None and nx is not None and ny is not None:
        if scenario == "add":
            folium.Marker(
                [qy, qx],
                tooltip="Candidate facility (new)",
                icon=folium.Icon(color="purple", icon="plus"),
            ).add_to(m2)

            folium.Marker(
                [ny, nx],
                tooltip=f"Existing nearest: {nearest_name}",
                icon=folium.Icon(color="green"),
            ).add_to(m2)

            folium.PolyLine([[qy, qx], [ny, nx]], color="purple", weight=3).add_to(m2)

        elif scenario == "remove":
            # Find 2nd-nearest for explanation/line
            second_idx = None
            second_dist = None
            for j, (x, y) in enumerate(coords_sample):
                if j == nearest_idx:
                    continue
                d = geodesic((qy, qx), (y, x)).km
                if second_dist is None or d < second_dist:
                    second_dist = d
                    second_idx = j

            if second_idx is not None:
                second_name = names_sample[second_idx]
                sx, sy = coords_sample[second_idx]

                folium.Marker(
                    [ny, nx],
                    tooltip=f"Removed facility: {nearest_name}",
                    icon=folium.Icon(color="red"),
                ).add_to(m2)

                folium.Marker(
                    [sy, sx],
                    tooltip=f"New nearest: {second_name}",
                    icon=folium.Icon(color="green"),
                ).add_to(m2)

                folium.PolyLine([[qy, qx], [sy, sx]], color="orange", weight=3).add_to(m2)

        elif scenario == "move":
            folium.Marker(
                [ny, nx],
                tooltip=f"Original location of {nearest_name}",
                icon=folium.Icon(color="green"),
            ).add_to(m2)

            folium.Marker(
                [qy, qx],
                tooltip=f"New location of {nearest_name}",
                icon=folium.Icon(color="purple", icon="arrow-up"),
            ).add_to(m2)

            folium.PolyLine([[qy, qx], [ny, nx]], color="purple", weight=3).add_to(m2)

    # Render static HTML map so dragging/zooming doesn't trigger reruns
    map_html = m2.get_root().render()
    components.html(map_html, height=500)

    # ---------- Scenario buttons ----------
    st.markdown("### Scenario actions")

    if not click:
        st.caption("Click on the left map first to enable scenario actions.")
    else:
        st.caption(
            "Use these buttons to overlay planning scenarios on the Voronoi map. "
            "The scenario stays active until you press **Clear scenario**."
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.button("Add facility here", key="btn_add", on_click=set_scenario_add, disabled=not bool(click))
    with c2:
        st.button("Remove nearest", key="btn_remove", on_click=set_scenario_remove, disabled=not bool(click))
    with c3:
        st.button("Move nearest here", key="btn_move", on_click=set_scenario_move, disabled=not bool(click))
    with c4:
        st.button("Clear scenario", key="btn_clear", on_click=clear_scenario)

    # ---------- Scenario text explanations ----------
    if click and nearest_idx is not None and scenario in {"add", "remove", "move"}:
        if scenario == "add":
            st.markdown("#### Scenario: Add a new facility at this point")
            base_dist = d_km
            st.write(
                f"- Current nearest facility: **{nearest_name}** at ≈ **{base_dist:.1f} km**."
            )
            cand_dists = [geodesic((qy, qx), (y, x)).km for (x, y) in coords_sample]
            base_dists = [geodesic((y, x), (ny, nx)).km for (x, y) in coords_sample]
            improved = sum(1 for cd, bd in zip(cand_dists, base_dists) if cd < bd)
            st.write(
                f"- Among the **{len(coords_sample)}** sampled locations, "
                f"**{improved}** would be closer to this new facility than to **{nearest_name}**."
            )

        elif scenario == "remove":
            st.markdown("#### Scenario: Remove the current nearest facility")
            second_idx = None
            second_dist = None
            for j, (x, y) in enumerate(coords_sample):
                if j == nearest_idx:
                    continue
                d = geodesic((qy, qx), (y, x)).km
                if second_dist is None or d < second_dist:
                    second_dist = d
                    second_idx = j

            if second_idx is not None:
                second_name = names_sample[second_idx]
                st.write(
                    f"- If **{nearest_name}** is removed, the new nearest facility is "
                    f"**{second_name}** at ≈ **{second_dist:.1f} km** "
                    f"(increase of ≈ **{(second_dist - d_km):.1f} km**)."
                )
            else:
                st.write("- No alternative facility found in the sampled set.")

        elif scenario == "move":
            st.markdown("#### Scenario: Move the nearest facility to this point")
            st.write(
                f"- Currently, **{nearest_name}** is at ≈ **{d_km:.1f} km** from this point. "
                f"If moved here, that distance becomes **0 km**."
            )
            moved_dists = [geodesic((qy, qx), (y, x)).km for (x, y) in coords_sample]
            old_dists = [geodesic((y, x), (ny, nx)).km for (x, y) in coords_sample]
            improved = sum(1 for md, od in zip(moved_dists, old_dists) if md < od)
            st.write(
                f"- Among the **{len(coords_sample)}** sampled locations, "
                f"**{improved}** would be closer to the moved facility at this point "
                f"than to its original location."
            )
