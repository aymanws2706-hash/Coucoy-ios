"""Estimation du bâti 2004 / 2014 / 2021 à partir de Landsat, entraînée sur ESA WorldCover 2021."""
import re, glob, numpy as np, rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from sklearn.ensemble import RandomForestClassifier

CRS = "EPSG:32630"
x0, y0, x1, y1 = [round(v, -1) for v in transform_bounds(4326, CRS, -6.00, 35.64, -5.66, 35.85)]
RES = 30
TR = from_origin(x0, y1, RES, RES); Wd = int((x1 - x0) / RES); Hd = int((y1 - y0) / RES)
SC = {"2004": ("ls/LT05_L1TP_201035_20040724_20180310_01_T1", ["1", "2", "3", "4", "5", "7"]),
      "2014": ("ls/LC08_L1TP_201035_20140805_20170420_01_T1", ["2", "3", "4", "5", "6", "7"]),
      "2021": ("ls/LC08_L1TP_201035_20210808_20210818_01_T1", ["2", "3", "4", "5", "6", "7"])}


def load(key):
    base, bands = SC[key]
    mtl = open(base + "_MTL.txt").read()
    sun = float(re.search(r"SUN_ELEVATION = ([\d.]+)", mtl).group(1))
    out = []
    for b in bands:
        m = float(re.search(rf"REFLECTANCE_MULT_BAND_{b} = ([-\dE.+]+)", mtl).group(1))
        a = float(re.search(rf"REFLECTANCE_ADD_BAND_{b} = ([-\dE.+]+)", mtl).group(1))
        with rasterio.open(f"{base}_B{b}.TIF") as s:
            arr = np.zeros((Hd, Wd), np.float32)
            reproject(s.read(1).astype(np.float32), arr, src_transform=s.transform, src_crs=s.crs, dst_transform=TR, dst_crs=CRS,
                      resampling=Resampling.bilinear, src_nodata=0, dst_nodata=0)
        refl = (arr * m + a) / np.sin(np.radians(sun)); refl[arr == 0] = np.nan
        out.append(refl)
    return np.stack(out)  # blue green red nir swir1 swir2


def feats(S):
    b, g, r, n, s1, s2 = S
    eps = 1e-6
    ndvi = (n - r) / (n + r + eps); ndbi = (s1 - n) / (s1 + n + eps); mndwi = (g - s1) / (g + s1 + eps)
    bright = S.mean(0)
    tex = ndi.generic_filter(np.nan_to_num(n), np.std, size=3)
    F = [b, g, r, n, s1, s2, ndvi, ndbi, mndwi, bright, tex]
    # per-scene robust normalization
    G = []
    for f in F:
        lo, hi = np.nanpercentile(f, 2), np.nanpercentile(f, 98)
        G.append((f - lo) / (hi - lo + 1e-6))
    return np.stack(G)


# WorldCover fraction built at 30 m
with rasterio.open("u_wc10.tif") as s:
    wc = s.read(1)
    fb = np.zeros((Hd, Wd), np.float32); fw = np.zeros((Hd, Wd), np.float32)
    reproject((wc == 50).astype(np.float32), fb, src_transform=s.transform, src_crs=CRS, dst_transform=TR, dst_crs=CRS, resampling=Resampling.average)
    reproject((wc == 80).astype(np.float32), fw, src_transform=s.transform, src_crs=CRS, dst_transform=TR, dst_crs=CRS, resampling=Resampling.average)

S = {k: load(k) for k in SC}
F = {k: feats(v) for k, v in S.items()}
valid = np.all([np.isfinite(F[k]).all(0) for k in F], axis=0) & (fw < 0.5)
X21 = F["2021"].reshape(len(F["2021"]), -1).T
lab = np.full(fb.shape, -1); lab[fb >= 0.7] = 1; lab[fb <= 0.02] = 0
m = (lab >= 0) & valid
idx = np.flatnonzero(m.ravel()); rng = np.random.default_rng(0)
idx1 = idx[lab.ravel()[idx] == 1]; idx0 = idx[lab.ravel()[idx] == 0]
sel = np.concatenate([rng.choice(idx1, min(20000, len(idx1)), replace=False), rng.choice(idx0, 40000, replace=False)])
clf = RandomForestClassifier(n_estimators=150, max_depth=16, n_jobs=-1, random_state=0, class_weight="balanced")
clf.fit(X21[sel], lab.ravel()[sel])
P = {}
for k in F:
    Xk = np.nan_to_num(F[k].reshape(len(F[k]), -1).T)
    P[k] = clf.predict_proba(Xk)[:, 1].reshape(fb.shape)
built21 = (fb >= 0.30) & valid
b14 = built21 & (P["2014"] > 0.5)
b04 = b14 & (P["2004"] > 0.5)
clean = lambda a: ndi.binary_opening(a, iterations=1) | (ndi.binary_erosion(a, iterations=1))
b14 = clean(b14) & built21; b04 = clean(b04) & b14
# accuracy check on 2021 itself
acc = ((P["2021"] > 0.5) == (fb >= 0.5))[valid & ((fb >= 0.7) | (fb <= 0.02))].mean()
print("self-accuracy 2021:", round(acc, 3))
np.savez_compressed("sprawl.npz", b04=b04, b14=b14, b21=built21, x0=x0, y1=y1, res=RES)
# true colour 2004 & 2021
for k in ("2004", "2021"):
    rgb = np.stack([S[k][2], S[k][1], S[k][0]], -1)
    rgb = np.clip((rgb - np.nanpercentile(rgb, 1)) / (np.nanpercentile(rgb, 99.3) - np.nanpercentile(rgb, 1)), 0, 1) ** 0.85
    np.save(f"ls_rgb_{k}.npy", np.nan_to_num(rgb).astype(np.float32))
# areas within commune
import geopandas as gpd, rasterio.features as rf
from shapely.ops import unary_union
ARR = gpd.read_parquet("a_arr.parquet")
city = rf.geometry_mask([unary_union(ARR.geometry.values)], fb.shape, TR, invert=True)
km2 = lambda a: a.sum() * RES * RES / 1e6
print("commune built km2: 2004", round(km2(b04 & city), 1), "2014", round(km2(b14 & city), 1), "2021", round(km2(built21 & city), 1))
print("region built km2: 2004", round(km2(b04), 1), "2014", round(km2(b14), 1), "2021", round(km2(built21), 1))
for r in ARR.itertuples():
    mm = rf.geometry_mask([r.geometry], fb.shape, TR, invert=True)
    print(r.arr, round(km2(b04 & mm), 2), round(km2(b14 & mm), 2), round(km2(built21 & mm), 2))
