// The bundled stock gallery (no uploads in v1). Keys match the seed creatives; since there
// are no real image files yet, previews render as a deterministic gradient derived from the
// key, so a creative always looks intentional. Real curated art lands in Phase 5.
export interface StockImage {
  key: string;
  label: string;
}

export const STOCK: StockImage[] = [
  { key: "stock/tech-1.jpg", label: "Tech" },
  { key: "stock/gaming-1.jpg", label: "Gaming" },
  { key: "stock/finance-1.jpg", label: "Finance" },
  { key: "stock/fashion-1.jpg", label: "Fashion" },
  { key: "stock/travel-1.jpg", label: "Travel" },
  { key: "stock/fitness-1.jpg", label: "Fitness" },
  { key: "stock/food-1.jpg", label: "Food" },
  { key: "stock/home-1.jpg", label: "Home" },
  { key: "stock/beauty-1.jpg", label: "Beauty" },
];

/** Stable 0..359 hue from an image key (or any string), for gradient placeholders. */
export function keyHue(key: string): number {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) % 360;
  return h;
}

export function stockGradient(key: string): string {
  const h = keyHue(key || "quanta");
  return `linear-gradient(135deg, hsl(${h} 70% 55%), hsl(${(h + 40) % 360} 72% 48%))`;
}
