import json, numpy as np, geopandas as gpd, rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.merge import merge
from rasterio.transform import from_origin

CRS = "EPSG:32630"
# region grid in UTM
xmin, ymin, xmax, ymax = transform_bounds(4326, CRS, -6.08, 35.47, -5.37, 35.93)
xmin, ymin, xmax, ymax = [round(v, -1) for v in (xmin, ymin, xmax, ymax)]
print("grid", xmin, ymin, xmax, ymax)

def grid(res):
    w = int((xmax - xmin) / res); h = int((ymax - ymin) / res)
    return from_origin(xmin, ymax, res, res), w, h

# WorldCover -> 10 m UTM
srcs = [rasterio.open(f) for f in ["wc_N33W009.tif", "wc_N33W006.tif"]]
wc, wtr = merge(srcs)
tr, w, h = grid(10)
out = np.zeros((h, w), np.uint8)
reproject(wc[0], out, src_transform=wtr, src_crs=srcs[0].crs, dst_transform=tr, dst_crs=CRS, resampling=Resampling.nearest)
with rasterio.open("u_wc10.tif", "w", driver="GTiff", width=w, height=h, count=1, dtype="uint8", crs=CRS, transform=tr, compress="deflate") as d:
    d.write(out, 1)
print("wc", out.shape)

# DEM -> 20 m UTM
with rasterio.open("dem.tif") as s:
    tr2, w2, h2 = grid(20)
    dem = np.zeros((h2, w2), np.float32)
    reproject(s.read(1), dem, src_transform=s.transform, src_crs=s.crs, dst_transform=tr2, dst_crs=CRS, resampling=Resampling.bilinear)
with rasterio.open("u_dem20.tif", "w", driver="GTiff", width=w2, height=h2, count=1, dtype="float32", crs=CRS, transform=tr2, compress="deflate") as d:
    d.write(dem, 1)
print("dem", dem.shape)

def nm(v):
    try:
        return json.loads(v).get("primary") if isinstance(v, str) else None
    except Exception:
        return None

for f in ["bld_city", "seg_region", "lu_region", "land_region", "water_region", "places_city", "div_region", "infra_region", "lc_region"]:
    g = gpd.read_parquet(f + ".parquet")
    if "names" in g:
        g["name"] = g["names"].apply(nm)
    if f == "div_region":
        g = g[g.subtype.isin(["locality", "localadmin", "neighborhood", "county", "region"])]
    g = g.to_crs(CRS)
    keep = [c for c in g.columns if c not in ("bbox", "names")]
    g[keep].to_parquet("u_" + f + ".parquet")
    print(f, len(g))
