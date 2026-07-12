// Inline profile editor. Interests / geo / age / gender come from the SAME catalog the ad
// cabinet targets on — and they literally shape which sponsored posts the auction serves you.
import { useEffect, useState } from "react";

import { cabinetApi, type TargetingOptions } from "../api/cabinet";
import type { ProfilePublic } from "../api/social";
import { socialApi } from "../api/social";

export function EditProfile({
  profile, onSaved,
}: {
  profile: ProfilePublic;
  onSaved: (p: ProfilePublic) => void;
}) {
  const [displayName, setDisplayName] = useState(profile.display_name);
  const [bio, setBio] = useState(profile.bio);
  const [interests, setInterests] = useState<string[]>(profile.interests);
  const [geo, setGeo] = useState(profile.geo);
  const [age, setAge] = useState(profile.age_band);
  const [gender, setGender] = useState(profile.gender);
  const [opts, setOpts] = useState<TargetingOptions | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    cabinetApi.targetingOptions().then(setOpts).catch(() => setOpts(null));
  }, []);

  function toggleInterest(i: string) {
    setInterests((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]));
  }

  async function save() {
    setBusy(true);
    try {
      const p = await socialApi.updateProfile({
        display_name: displayName, bio, interests, geo, age_band: age, gender,
      });
      onSaved(p);
    } catch {
      /* leave the form open so edits aren't lost */
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card edit-profile">
      <div className="field">
        <label>Display name</label>
        <input className="input" value={displayName} maxLength={60} onChange={(e) => setDisplayName(e.target.value)} />
      </div>
      <div className="field">
        <label>Bio</label>
        <textarea className="textarea" value={bio} maxLength={280} onChange={(e) => setBio(e.target.value)} />
      </div>
      <div className="field">
        <label>Interests <span className="muted">— shape the sponsored posts you see</span></label>
        <div className="chip-set">
          {(opts?.interests ?? []).map((i) => (
            <button
              key={i}
              type="button"
              className={`chip-toggle ${interests.includes(i) ? "on" : ""}`}
              onClick={() => toggleInterest(i)}
            >
              {i}
            </button>
          ))}
        </div>
      </div>
      <div className="row-2">
        <div className="field">
          <label>Location</label>
          <select className="select" value={geo} onChange={(e) => setGeo(e.target.value)}>
            <option value="">—</option>
            {(opts?.geos ?? []).map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Age</label>
          <select className="select" value={age} onChange={(e) => setAge(e.target.value)}>
            <option value="">—</option>
            {(opts?.age_bands ?? []).map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Gender</label>
        <select className="select" value={gender} onChange={(e) => setGender(e.target.value)}>
          <option value="">—</option>
          {(opts?.genders ?? []).map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
      </div>
      <div className="edit-foot">
        <button className="btn primary" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save profile"}
        </button>
      </div>
    </div>
  );
}
