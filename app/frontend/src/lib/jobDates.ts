// Libellés de dates des offres (publication / expiration), partagés par le
// feed connecté et les pages d'offres publiques.

// Human-readable expiry label. `urgent` within 7 days, `soon` within 3 days.
export function expiryInfo(
  validThrough?: string
): { label: string; urgent: boolean; soon: boolean; days: number } | null {
  if (!validThrough) return null;
  const d = new Date(`${validThrough}T00:00:00`);
  if (isNaN(d.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((d.getTime() - today.getTime()) / 86400000);
  if (days < 0) return null; // expired offers are filtered out upstream
  const soon = days <= 3;
  if (days === 0) return { label: "Expire aujourd'hui", urgent: true, soon, days };
  if (days === 1) return { label: 'Expire demain', urgent: true, soon, days };
  if (days <= 7) return { label: `Expire dans ${days} jours`, urgent: true, soon, days };
  const dateStr = d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  return { label: `Expire le ${dateStr}`, urgent: false, soon: false, days };
}

// Human-readable "published" label. Prefer the source's posted_date when it's a
// sane value, otherwise fall back to created_at (when the offer entered our DB),
// because some sources emit bogus dates (epoch-ish or in the future).
export function publishedInfo(postedDate?: string, createdAt?: string): { label: string } | null {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const minValid = new Date(today);
  minValid.setFullYear(minValid.getFullYear() - 1); // ignore offers "published" > 1 an ago

  const parse = (s?: string) => {
    if (!s) return null;
    const d = new Date(s.length <= 10 ? `${s}T00:00:00` : s);
    return isNaN(d.getTime()) ? null : d;
  };

  let d = parse(postedDate);
  if (!d || d.getTime() > today.getTime() || d.getTime() < minValid.getTime()) {
    d = parse(createdAt); // posted_date absent / futur / trop vieux → repli
  }
  if (!d) return null;

  const day = new Date(d);
  day.setHours(0, 0, 0, 0);
  const days = Math.round((today.getTime() - day.getTime()) / 86400000);
  if (days <= 0) return { label: "Publié aujourd'hui" };
  if (days === 1) return { label: 'Publié hier' };
  if (days <= 30) return { label: `Publié il y a ${days} jours` };
  const dateStr = d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  return { label: `Publié le ${dateStr}` };
}
