// Ambient "quanta" motif: electrons tracing tilted elliptical orbits around a glowing
// nucleus, plus a few drifting particles. Pure SVG + SMIL/CSS, theme-aware, decorative
// (aria-hidden, pointer-events: none). Honors prefers-reduced-motion.
export function AtomBackground() {
  const reduce =
    typeof window !== "undefined" &&
    !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  const orbits = [
    { angle: 0, dur: "15s", alt: false },
    { angle: 60, dur: "19s", alt: true },
    { angle: 120, dur: "23s", alt: false },
  ];
  // Ellipse centered at (200,200), rx=150 ry=54 — the electron path.
  const PATH = "M 50,200 a 150,54 0 1,0 300,0 a 150,54 0 1,0 -300,0";

  return (
    <div className="atom-bg" aria-hidden>
      <svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="q-core" cx="50%" cy="50%" r="50%">
            <stop className="s1" offset="0%" />
            <stop className="s2" offset="100%" />
          </radialGradient>
          <filter id="q-glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="9" />
          </filter>
        </defs>

        {orbits.map((o, i) => (
          <g key={i} transform={`rotate(${o.angle} 200 200)`}>
            <ellipse className="orbit-ring" cx="200" cy="200" rx="150" ry="54" />
            <circle
              className={`electron${o.alt ? " alt" : ""}`}
              r="5"
              cx={reduce ? 350 : undefined}
              cy={reduce ? 200 : undefined}
            >
              {!reduce && (
                <animateMotion dur={o.dur} repeatCount="indefinite" path={PATH} />
              )}
            </circle>
          </g>
        ))}

        {/* nucleus */}
        <circle className="nucleus-glow" cx="200" cy="200" r="26" filter="url(#q-glow)" />
        <circle cx="200" cy="200" r="13" fill="url(#q-core)" />

        {/* drifting quanta */}
        <circle className="spark a" cx="92" cy="118" r="2.5" />
        <circle className="spark b" cx="322" cy="150" r="2" />
        <circle className="spark c" cx="300" cy="298" r="2.5" />
        <circle className="spark a" cx="108" cy="292" r="2" />
      </svg>
    </div>
  );
}
