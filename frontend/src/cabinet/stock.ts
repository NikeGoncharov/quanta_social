// The bundled stock gallery. There are no binary assets in v1 (uploads + an AI library are v2);
// instead every image key renders as deterministic generative "art" — a category-tinted mesh
// gradient — so a creative or a post image always looks intentional and a category reads at a
// glance. Keys follow `stock/<interest>-<n>.jpg`; the backend seeds posts with matching keys.
export interface StockImage {
  key: string;
  label: string;
}

// One anchor hue per world interest, so tech reads blue, food amber, pets aqua, and so on — the
// gallery feels curated by category rather than random. Keys not in this map fall back to a hash.
const CATEGORY_HUE: Record<string, number> = {
  tech: 210, gaming: 275, finance: 150, fashion: 330, travel: 190,
  fitness: 14, food: 35, autos: 222, beauty: 320, sports: 100,
  music: 258, parenting: 46, home: 24, pets: 176, education: 240,
};

const CATEGORY_LABEL: Record<string, string> = {
  tech: "Tech", gaming: "Gaming", finance: "Finance", fashion: "Fashion", travel: "Travel",
  fitness: "Fitness", food: "Food", autos: "Autos", beauty: "Beauty", sports: "Sports",
  music: "Music", parenting: "Parenting", home: "Home", pets: "Pets", education: "Education",
};

// The picker shown in the composer / creative editor: one swatch per category.
export const STOCK: StockImage[] = Object.keys(CATEGORY_HUE).map((cat) => ({
  key: `stock/${cat}-1.jpg`,
  label: CATEGORY_LABEL[cat],
}));

/** Stable 0..359 hue from any string, for keys with no category anchor. */
export function keyHue(key: string): number {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) % 360;
  return h;
}

function hash(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function categoryOf(key: string): string | null {
  const m = /^stock\/([a-z]+)-/.exec(key);
  return m && m[1] in CATEGORY_HUE ? m[1] : null;
}

/** A deterministic, category-tinted mesh-gradient background for an image key. Two off-center
 *  color blooms over a diagonal base — reads as abstract "cover art", stable per key, and works
 *  on light and dark alike. Returned as a CSS `background` value (layers comma-separated). */
export function stockArt(key: string): string {
  const k = key || "quanta";
  const cat = categoryOf(k);
  const base = cat ? CATEGORY_HUE[cat] : keyHue(k);
  const v = hash(k);
  const b = (base + 34) % 360;
  const c = (base + 320) % 360;
  const p1x = 16 + (v % 30);
  const p1y = 12 + ((v >> 3) % 32);
  const p2x = 60 + ((v >> 7) % 28);
  const p2y = 58 + ((v >> 11) % 30);
  return [
    `radial-gradient(60% 60% at ${p1x}% ${p1y}%, hsl(${base} 85% 63% / 0.95), transparent 68%)`,
    `radial-gradient(55% 55% at ${p2x}% ${p2y}%, hsl(${b} 80% 56% / 0.9), transparent 70%)`,
    `linear-gradient(135deg, hsl(${base} 68% 47%), hsl(${c} 70% 40%))`,
  ].join(", ");
}

// Back-compat alias: earlier phases call `stockGradient(key)`. The art generator supersedes the
// old two-stop gradient; the name is kept so existing call sites keep working.
export const stockGradient = stockArt;
