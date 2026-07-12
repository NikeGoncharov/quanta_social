// Chip multiselect over the world's targeting dimensions + a live audience gauge. An empty
// group means "all" (no constraint) — matching the engine's targeting semantics.
import { useEffect, useState } from "react";

import { cabinetApi, type AudienceResult, type TargetingOptions, type TargetingSpec } from "../api/cabinet";
import { AudienceGauge } from "./AudienceGauge";

type Group = "interests" | "geos" | "age_bands" | "genders";
const GROUPS: { key: Group; label: string }[] = [
  { key: "interests", label: "Interests" },
  { key: "geos", label: "Geos" },
  { key: "age_bands", label: "Age" },
  { key: "genders", label: "Gender" },
];

export function TargetingEditor({
  value,
  onChange,
  options,
}: {
  value: TargetingSpec;
  onChange: (t: TargetingSpec) => void;
  options: TargetingOptions | null;
}) {
  const [aud, setAud] = useState<AudienceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const key = JSON.stringify(value);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const id = setTimeout(() => {
      cabinetApi
        .audience(value)
        .then((r) => alive && (setAud(r), setLoading(false)))
        .catch(() => alive && setLoading(false));
    }, 250);
    return () => {
      alive = false;
      clearTimeout(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const toggle = (group: Group, item: string) => {
    const cur = value[group];
    const next = cur.includes(item) ? cur.filter((x) => x !== item) : [...cur, item];
    onChange({ ...value, [group]: next });
  };

  return (
    <div className="stack">
      <AudienceGauge
        audience={aud?.audience ?? 0}
        reachPct={aud?.reach_pct ?? 0}
        segments={aud?.segments ?? 0}
        loading={loading}
      />
      {GROUPS.map((g) => (
        <div className="field" key={g.key}>
          <label>
            {g.label}
            {value[g.key].length === 0 && <span className="hint"> · all</span>}
          </label>
          <div className="chip-set">
            {(options?.[g.key] ?? []).map((item) => (
              <button
                type="button"
                key={item}
                className={`chip-toggle ${value[g.key].includes(item) ? "on" : ""}`}
                onClick={() => toggle(g.key, item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
