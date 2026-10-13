"""Minimal Overture reader over HTTPS range requests (through the agent proxy)."""
import sys, re, json, concurrent.futures as cf
import requests, fsspec
import pyarrow.parquet as pq, pyarrow as pa
import geopandas as gpd
from shapely import wkb

BASE = "https://s3.us-west-2.amazonaws.com/overturemaps-us-west-2"
REL = "release/2026-09-23.0"
S = requests.Session()
S.verify = "/root/.ccr/ca-bundle.crt"
HFS = fsspec.filesystem("http", client_kwargs={"trust_env": True}, block_size=2 ** 20)


def list_keys(prefix):
    keys, tok = [], None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if tok:
            params["continuation-token"] = tok
        r = S.get(BASE, params=params, timeout=60); r.raise_for_status()
        keys += re.findall(r"<Key>([^<]+\.parquet)</Key>", r.text)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", r.text)
        if not m:
            return keys
        tok = m.group(1)


def rg_hits(key, bb):
    xmin, ymin, xmax, ymax = bb
    f = HFS.open(f"{BASE}/{key}", "rb")
    pf = pq.ParquetFile(f)
    md = pf.metadata
    names = pf.schema_arrow.names
    # locate bbox leaf column indices
    idx = {}
    for i in range(md.num_columns):
        p = md.schema.column(i).path
        if p in ("bbox.xmin", "bbox.xmax", "bbox.ymin", "bbox.ymax"):
            idx[p] = i
    hits = []
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        st = {k: rg.column(i).statistics for k, i in idx.items()}
        try:
            if st["bbox.xmin"].min > xmax or st["bbox.xmax"].max < xmin or st["bbox.ymin"].min > ymax or st["bbox.ymax"].max < ymin:
                continue
        except Exception:
            pass
        hits.append(g)
    return key, hits, pf


def fetch(theme, typ, bb, out, columns=None):
    keys = list_keys(f"{REL}/theme={theme}/type={typ}/")
    print(theme, typ, len(keys), "files", flush=True)
    frames = []
    with cf.ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda k: rg_hits(k, bb), keys))
    for key, hits, pf in res:
        if not hits:
            continue
        print("  ", key.split("/")[-1][:40], len(hits), "row groups", flush=True)
        t = pf.read_row_groups(hits, columns=columns)
        d = t.to_pandas()
        bbx = d["bbox"].apply(pd_bb)
        keep = [(b[0] <= bb[2] and b[2] >= bb[0] and b[1] <= bb[3] and b[3] >= bb[1]) for b in bbx]
        d = d[keep]
        frames.append(d)
    import pandas as pd
    if not frames:
        print("none"); return
    d = pd.concat(frames, ignore_index=True)
    d["geometry"] = d["geometry"].apply(lambda b: wkb.loads(bytes(b)))
    for c in d.columns:
        if c != "geometry" and d[c].dtype == object:
            d[c] = d[c].apply(lambda v: json.dumps(v, default=str) if isinstance(v, (dict, list)) or hasattr(v, "tolist") else v)
    g = gpd.GeoDataFrame(d, geometry="geometry", crs=4326)
    g.to_parquet(out)
    print(theme, typ, len(g), "->", out, flush=True)


def pd_bb(b):
    return (b["xmin"], b["ymin"], b["xmax"], b["ymax"])


if __name__ == "__main__":
    theme, typ, out = sys.argv[1], sys.argv[2], sys.argv[3]
    bb = tuple(float(v) for v in sys.argv[4].split(","))
    cols = sys.argv[5].split(",") if len(sys.argv) > 5 else None
    fetch(theme, typ, bb, out, cols)
