import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import PublicHeader from '../components/PublicHeader';
import { usePublicJobs } from '../hooks/useApi';
import { publishedInfo } from '../lib/jobDates';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, MapPin, Building2, Briefcase, Loader2, ArrowRight } from 'lucide-react';

const PAGE = 30;

/** Liste publique des offres actives (indexable, sans compte). */
export default function PublicJobs() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const [input, setInput] = useState(q);
  const [limit, setLimit] = useState(PAGE);
  const { data, isLoading, isFetching } = usePublicJobs(q, limit);
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  useEffect(() => {
    document.title = "Offres d'emploi en Côte d'Ivoire et Afrique de l'Ouest | EmploiCentral";
  }, []);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setLimit(PAGE);
    setParams(input.trim() ? { q: input.trim() } : {});
  };

  return (
    <div className="min-h-screen app-surface">
      <PublicHeader />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
          Offres d&apos;emploi en Côte d&apos;Ivoire et Afrique de l&apos;Ouest
        </h1>
        <p className="text-slate-500 mt-1 mb-6">
          {total > 0 ? `${total} offres actives` : 'Offres actives'}, mises à jour plusieurs fois par jour.
        </p>

        <form onSubmit={submit} className="flex gap-2 mb-6">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Poste, entreprise, ville, secteur…"
              className="pl-9 bg-white"
              aria-label="Rechercher une offre"
            />
          </div>
          <Button type="submit" className="bg-brand-gradient hover:opacity-95">Rechercher</Button>
        </form>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
          </div>
        ) : items.length === 0 ? (
          <p className="text-center text-slate-500 py-16">Aucune offre ne correspond à votre recherche.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((job) => {
              const pub = publishedInfo(job.posted_date, job.created_at);
              return (
                <li key={job.id}>
                  <Link to={`/offres/${job.id}`} className="block">
                    <Card className="border-slate-200/70 shadow-sm card-lift">
                      <CardContent className="p-4 sm:p-5">
                        <h2 className="font-semibold text-slate-900">{job.title}</h2>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-sm text-slate-500">
                          <span className="flex items-center gap-1"><Building2 className="w-4 h-4" />{job.company}</span>
                          {job.location && (
                            <span className="flex items-center gap-1"><MapPin className="w-4 h-4" />{job.location}</span>
                          )}
                          {job.contract_type && job.contract_type !== 'Non précisé' && (
                            <span className="flex items-center gap-1"><Briefcase className="w-4 h-4" />{job.contract_type}</span>
                          )}
                        </div>
                        {pub && <p className="text-xs text-slate-400 mt-2">{pub.label}</p>}
                      </CardContent>
                    </Card>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}

        {items.length < total && (
          <div className="flex justify-center mt-6">
            <Button variant="outline" onClick={() => setLimit((l) => l + PAGE)} disabled={isFetching}>
              {isFetching ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Voir plus d&apos;offres
            </Button>
          </div>
        )}

        <Card className="mt-10 border-blue-200 bg-blue-50/60">
          <CardContent className="p-5 sm:flex items-center justify-between gap-4">
            <div>
              <p className="font-semibold text-slate-900">Trouvez les offres faites pour vous</p>
              <p className="text-sm text-slate-600">
                Compte gratuit : score de compatibilité avec votre CV, CV ATS sur mesure et alertes WhatsApp.
              </p>
            </div>
            <Link to="/login" className="shrink-0 mt-3 sm:mt-0 inline-block">
              <Button className="bg-warm-gradient hover:opacity-95">
                Créer mon compte <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
