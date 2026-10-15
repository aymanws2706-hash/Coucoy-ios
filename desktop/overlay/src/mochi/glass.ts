// Personal build: the liquid-glass droplet. One painter for every place the
// character is drawn (island, launch greeting, file drop), so they all match.
//
// Layers, back to front: a clear, slightly blue body; the mood colour pooling
// at the bottom like tinted water; a bright caustic where light focuses inside;
// a fresnel glow along the edge; a thin rim that catches the light top-left;
// and two specular highlights.

export type GlassRGB = readonly [number, number, number]; // 0…1

const rgba = (c: GlassRGB, a: number) =>
  `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${a})`;

const GLASS: GlassRGB = [0.78, 0.86, 1];

/**
 * Paints the droplet into `path` (already in the body's local space, centred on
 * 0,0, about rx × ry). `tint` is the mood colour, `amount` how much of it.
 */
export function paintGlass(
  x: CanvasRenderingContext2D,
  path: Path2D,
  R: number,
  rx: number,
  ry: number,
  tint: GlassRGB | null,
  amount: number,
  t = performance.now() / 1000,
) {
  x.save();

  // Body: clear glass, denser toward the bottom where it's thicker.
  const body = x.createLinearGradient(0, -ry, 0, ry);
  body.addColorStop(0, rgba(GLASS, 0.2));
  body.addColorStop(1, rgba(GLASS, 0.42));
  x.fillStyle = body;
  x.fill(path);

  x.clip(path);

  // Mood colour pooling at the bottom, sloshing a little.
  if (tint && amount > 0.01) {
    const slosh = Math.sin(t * 1.7) * rx * 0.12;
    const pool = x.createRadialGradient(slosh, ry * 0.9, 0, slosh, ry * 0.6, R * 1.25);
    pool.addColorStop(0, rgba(tint, 0.85 * amount));
    pool.addColorStop(0.55, rgba(tint, 0.4 * amount));
    pool.addColorStop(1, rgba(tint, 0));
    x.fillStyle = pool;
    x.fillRect(-rx * 1.5, -ry * 1.5, rx * 3, ry * 3);
  }

  // Caustic: light focused near the bottom inside the drop.
  const cy = ry * 0.58;
  const caustic = x.createRadialGradient(0, cy, 0, 0, cy, rx * 0.7);
  caustic.addColorStop(0, "rgba(255,255,255,0.42)");
  caustic.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = caustic;
  x.beginPath();
  x.ellipse(0, cy, rx * 0.62, ry * 0.26, 0, 0, Math.PI * 2);
  x.fill();

  // Fresnel: glass looks brighter at the edges than in the middle.
  const fres = x.createRadialGradient(0, 0, R * 0.55, 0, 0, R * 1.2);
  fres.addColorStop(0, "rgba(255,255,255,0)");
  fres.addColorStop(1, "rgba(255,255,255,0.38)");
  x.fillStyle = fres;
  x.fillRect(-rx * 1.5, -ry * 1.5, rx * 3, ry * 3);

  // A slow sheen sliding across, like light moving over water.
  const s = ((t * 0.18) % 1) * 3 - 1;
  const sheen = x.createLinearGradient(rx * (s - 0.4), -ry, rx * (s + 0.4), ry);
  sheen.addColorStop(0, "rgba(255,255,255,0)");
  sheen.addColorStop(0.5, "rgba(255,255,255,0.1)");
  sheen.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = sheen;
  x.fillRect(-rx * 1.5, -ry * 1.5, rx * 3, ry * 3);

  x.restore();

  // Rim: bright top-left, fading, catching light again bottom-right.
  x.save();
  const rim = x.createLinearGradient(-rx, -ry, rx, ry);
  rim.addColorStop(0, "rgba(255,255,255,0.95)");
  rim.addColorStop(0.45, "rgba(255,255,255,0.18)");
  rim.addColorStop(0.75, "rgba(255,255,255,0.12)");
  rim.addColorStop(1, "rgba(255,255,255,0.6)");
  x.strokeStyle = rim;
  x.lineWidth = Math.max(0.8, R * 0.045);
  x.stroke(path);
  x.restore();

  // Specular highlights: a long soft one and a small sharp one.
  x.save();
  x.clip(path);
  x.translate(-rx * 0.4, -ry * 0.5);
  x.rotate(-0.55);
  const spec = x.createRadialGradient(0, 0, 0, 0, 0, R * 0.36);
  spec.addColorStop(0, "rgba(255,255,255,0.9)");
  spec.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = spec;
  x.beginPath();
  x.ellipse(0, 0, R * 0.36, R * 0.12, 0, 0, Math.PI * 2);
  x.fill();
  x.restore();

  x.save();
  x.fillStyle = "rgba(255,255,255,0.85)";
  x.beginPath();
  x.arc(rx * 0.46, -ry * 0.36, Math.max(0.6, R * 0.055), 0, Math.PI * 2);
  x.fill();
  x.restore();
}

/** Wobble for a liquid outline: multiply a point's radius by this. */
export function wobble(angle: number, t: number, amount: number): number {
  return 1 + amount * (0.028 * Math.sin(3 * angle + t * 2.1) + 0.018 * Math.sin(5 * angle - t * 3.3));
}
