import { Link } from 'react-router-dom';
import { Award, ListChecks, Clock, Infinity as InfinityIcon, ArrowRight } from 'lucide-react';

/**
 * Vitrine des certifications payantes (cours protégés `/cours/:slug`).
 * Rend la page de vente découvrable depuis l'onglet Formations — sans ce bloc,
 * `/cours/pmp` n'était accessible par aucun lien de l'app.
 *
 * Chaque entrée correspond à un slug de `PAID_COURSES` (backend course_access.py).
 * Ajouter une carte ici pour chaque nouvelle certification payante.
 */
type Cert = {
  slug: string;
  title: string;
  tagline: string;
  price: string;
  highlights: { icon: React.ElementType; label: string }[];
};

const CERTIFICATIONS: Cert[] = [
  {
    slug: 'pmp',
    title: 'Certification PMP®',
    tagline:
      "Simulation d'examen complète alignée sur le PMBOK® 7 : entraîne-toi comme le jour J et arrive en confiance.",
    price: '20 000 FCFA',
    highlights: [
      { icon: ListChecks, label: '900+ questions' },
      { icon: Clock, label: 'Examen chronométré' },
      { icon: InfinityIcon, label: 'Tentatives illimitées' },
    ],
  },
];

export default function CertificationSpotlight() {
  if (CERTIFICATIONS.length === 0) return null;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Award className="h-5 w-5 text-primary" />
          Certifications professionnelles
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Prépare une certification reconnue et valorise ton profil auprès des recruteurs.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {CERTIFICATIONS.map((c) => (
          <Link
            key={c.slug}
            to={`/cours/${c.slug}`}
            className="group relative overflow-hidden rounded-xl border border-primary/20 bg-brand-gradient p-5 text-white shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-start justify-between gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs font-semibold backdrop-blur">
                <Award className="h-3.5 w-3.5" /> Certification
              </span>
              <span className="rounded-full bg-white/15 px-2.5 py-1 text-xs font-bold backdrop-blur">
                {c.price}
              </span>
            </div>

            <h3 className="mt-3 text-xl font-bold leading-tight">{c.title}</h3>
            <p className="mt-1.5 text-sm text-white/85">{c.tagline}</p>

            <div className="mt-4 flex flex-wrap gap-2">
              {c.highlights.map((h) => (
                <span
                  key={h.label}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-white/12 px-2.5 py-1 text-xs backdrop-blur"
                >
                  <h.icon className="h-3.5 w-3.5" /> {h.label}
                </span>
              ))}
            </div>

            <div className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold">
              Découvrir la préparation
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
