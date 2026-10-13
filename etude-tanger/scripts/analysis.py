import json, numpy as np, geopandas as gpd, pandas as pd, rasterio, rasterio.features
from shapely.ops import unary_union

P = gpd.read_parquet("u_places_city.parquet")
P["prim"] = P["taxonomy"].apply(lambda t: json.loads(t).get("primary") if isinstance(t, str) else None)
LODG = {"hotel", "lodging", "hostel", "resort", "bed_and_breakfast", "holiday_rental_home", "motel", "service_apartment"}
SCHO = {"school", "elementary_school", "middle_school", "high_school", "preschool", "public_school", "private_school", "day_care_preschool"}
HEAL = {"hospital", "health_care", "doctors_office", "pediatric_clinic", "dialysis_clinic", "pharmacy"}
SITE = {"historic_site", "history_museum", "museum", "art_museum", "modern_art_museum", "monument", "civilization_museum", "community_museum"}
P["fam"] = np.select([P.prim.isin(LODG), P.prim.isin(SCHO), P.prim.isin(HEAL), P.prim.isin(SITE), P.prim.eq("beach")],
                     ["lodging", "school", "health", "site", "beach"], default="")
P[P.fam != ""][["name", "prim", "fam", "geometry"]].to_parquet("a_places.parquet")

D = gpd.read_parquet("u_div_region.parquet")
ARR = D[D.subtype.eq("neighborhood") & D.name.str.startswith("arrondissement", na=False)].copy()
ARR["arr"] = ARR.name.str.replace("arrondissement de ", "").str.split(" ").str[0]
ARR["arr"] = ARR["arr"].replace({"Bni": "Beni Makada", "Tanger-Medina": "Tanger-Médina", "Charf-Souani": "Charf-Souani", "Charf-Mghogha": "Charf-Mghogha"})
POP = {"Tanger-Médina": (243082, 343535), "Beni Makada": (386191, 567465), "Charf-Mghogha": (201122, 252656), "Charf-Souani": (117557, 111772)}
ARR["pop14"] = ARR.arr.map(lambda a: POP[a][0]); ARR["pop24"] = ARR.arr.map(lambda a: POP[a][1])
ARR["area_km2"] = ARR.area / 1e6
ARR[["arr", "pop14", "pop24", "area_km2", "geometry"]].to_parquet("a_arr.parquet")

wc = rasterio.open("u_wc10.tif"); W = wc.read(1)
stops = gpd.read_parquet("u_infra_region.parquet"); stops = stops[stops["class"].eq("bus_stop")]
stopbuf = unary_union(stops.buffer(300).values)
stopmask = rasterio.features.geometry_mask([stopbuf], W.shape, wc.transform, invert=True)
lu = gpd.read_parquet("u_lu_region.parquet"); parks = lu[lu.subtype.eq("park")]
rows = []
for _, r in ARR.iterrows():
    m = rasterio.features.geometry_mask([r.geometry], W.shape, wc.transform, invert=True)
    built = (W == 50) & m
    pts = P[P.within(r.geometry)]
    rows.append(dict(arr=r.arr, pop14=r.pop14, pop24=r.pop24, area=r.area_km2,
                     built_km2=built.sum() * 100 / 1e6, tree_km2=((W == 10) & m).sum() * 100 / 1e6,
                     lodging=(pts.fam == "lodging").sum(), school=(pts.fam == "school").sum(), health=(pts.fam == "health").sum(),
                     site=(pts.fam == "site").sum(), stops=stops.within(r.geometry).sum(),
                     served=(built & stopmask).sum() / max(1, built.sum()),
                     park_ha=parks.clip(r.geometry).area.sum() / 1e4, upark_ha=parks[parks.area < 30e4].clip(r.geometry).area.sum() / 1e4))
T = pd.DataFrame(rows)
T["growth"] = T.pop24 / T.pop14 - 1
T["dens"] = T.pop24 / T.built_km2
for k in ["lodging", "school", "health", "stops"]:
    T[k + "_10k"] = T[k] / T.pop24 * 1e4
T["park_m2_hab"] = T.park_ha * 1e4 / T.pop24
T["upark_m2_hab"] = T.upark_ha * 1e4 / T.pop24
pd.set_option("display.width", 250)
print(T.round(3).to_string())
T.to_csv("a_table.csv", index=False)

# coast analysis: distance of lodging to sea
import scipy.ndimage as ndi
lab, n = ndi.label(W == 80)
sizes = ndi.sum(np.ones_like(lab), lab, range(n + 1)); sizes[0] = 0
sea = lab == np.argmax(sizes)
np.save("a_sea.npy", sea)
dist = ndi.distance_transform_edt(~sea) * 10
def d2sea(geom):
    r, c = rasterio.transform.rowcol(wc.transform, geom.x, geom.y)
    return dist[r, c]
city = unary_union(ARR.geometry.values)
for fam in ["lodging", "school", "health"]:
    q = P[(P.fam == fam) & P.within(city)]
    dd = np.array([d2sea(g) for g in q.geometry])
    print(fam, len(q), "median dist to sea m:", int(np.median(dd)), "share <1km:", round((dd < 1000).mean(), 3))
cm = rasterio.features.geometry_mask([city], W.shape, wc.transform, invert=True)
bd = dist[(W == 50) & cm]
print("built-up share <1km of sea:", round((bd < 1000).mean(), 3), "median", int(np.median(bd)))
print("total stops", len(stops), "city served", round(((W == 50) & cm & stopmask).sum() / ((W == 50) & cm).sum(), 3))

for a in ARR.itertuples():
    m = rasterio.features.geometry_mask([a.geometry], W.shape, wc.transform, invert=True)
    print(a.arr, "median dist built->sea m", int(np.median(dist[(W == 50) & m])))
for fam in ["lodging", "school", "health"]:
    q = P[(P.fam == fam) & P.within(city)]
    dd = np.array([d2sea(g) for g in q.geometry]); print(fam, "share<500", round((dd<500).mean(),3), "share<1000", round((dd<1000).mean(),3))
