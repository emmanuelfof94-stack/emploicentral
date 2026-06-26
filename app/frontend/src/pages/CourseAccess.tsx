import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useCourseAccess, useCourseAccessActions } from '../hooks/useApi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Lock, Loader2, CheckCircle2, Clock, Smartphone } from 'lucide-react';

export default function CourseAccess() {
  const { slug = '' } = useParams();
  const { data: access, isLoading, refetch } = useCourseAccess(slug);
  const { requestAccess } = useCourseAccessActions();
  const [ref, setRef] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [contentUrl, setContentUrl] = useState<string | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);

  // Une fois l'accès accordé, on récupère le HTML protégé (avec le JWT) et on le
  // rend dans un iframe via une URL blob (le lien direct reste inaccessible).
  useEffect(() => {
    let created: string | null = null;
    if (access?.has_access && !contentUrl) {
      setLoadingContent(true);
      const token = localStorage.getItem('token');
      fetch(`/api/v1/course-access/${slug}/content`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((r) => {
          if (!r.ok) throw new Error(String(r.status));
          return r.text();
        })
        .then((html) => {
          const blob = new Blob([html], { type: 'text/html' });
          created = URL.createObjectURL(blob);
          setContentUrl(created);
        })
        .catch(() => toast.error('Impossible de charger le cours.'))
        .finally(() => setLoadingContent(false));
    }
    return () => {
      if (created) URL.revokeObjectURL(created);
    };
  }, [access?.has_access, slug, contentUrl]);

  const onSubmit = async () => {
    if (!ref.trim()) {
      toast.error('Indiquez le numéro / la référence utilisé pour payer.');
      return;
    }
    setSubmitting(true);
    try {
      await requestAccess(slug, ref.trim());
      toast.success('Demande envoyée ! Nous validons votre paiement sous peu.');
      await refetch();
    } catch {
      toast.error("Échec de l'envoi. Réessayez.");
    } finally {
      setSubmitting(false);
    }
  };

  // Accès accordé → cours en plein écran.
  if (access?.has_access) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        {loadingContent || !contentUrl ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" /> Chargement du cours…
          </div>
        ) : (
          <iframe
            title={access.title}
            src={contentUrl}
            className="w-full border-0"
            style={{ height: 'calc(100vh - 64px)' }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-xl mx-auto px-4 sm:px-6 py-10">
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
          </div>
        ) : (
          <Card className="card-lift">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lock className="h-5 w-5 text-primary" /> Cours payant
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div>
                <p className="font-semibold">{access?.title}</p>
                <p className="text-2xl font-bold text-primary mt-1">{access?.price}</p>
              </div>

              {access?.status === 'pending' ? (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-amber-800 flex gap-2">
                  <Clock className="h-5 w-5 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium">Paiement en cours de vérification</p>
                    <p className="text-sm mt-1">
                      Nous validons votre paiement. Vous recevrez une notification dès que l'accès
                      sera débloqué.
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="rounded-lg bg-muted p-4 space-y-2">
                    <p className="text-sm font-medium flex items-center gap-2">
                      <Smartphone className="h-4 w-4" /> Comment payer
                    </p>
                    <ol className="text-sm text-muted-foreground list-decimal pl-5 space-y-1">
                      <li>
                        Envoyez <b>{access?.price}</b> par <b>Wave</b> ou <b>Orange Money</b> au
                        numéro :
                      </li>
                      <li className="list-none -ml-5">
                        <span className="font-mono text-base font-bold text-foreground">
                          {access?.payment_number}
                        </span>
                      </li>
                      <li>Notez le numéro que vous avez utilisé pour payer.</li>
                      <li>Saisissez-le ci-dessous et cliquez « J'ai payé ».</li>
                    </ol>
                  </div>

                  {access?.status === 'rejected' && (
                    <p className="text-sm text-destructive">
                      Votre précédent paiement n'a pas été confirmé. Vérifiez et soumettez à nouveau.
                    </p>
                  )}

                  <div className="space-y-2">
                    <Label htmlFor="ref">Votre numéro / référence de paiement</Label>
                    <Input
                      id="ref"
                      placeholder="Ex. 0749109013"
                      value={ref}
                      onChange={(e) => setRef(e.target.value)}
                    />
                  </div>

                  <Button onClick={onSubmit} disabled={submitting} className="bg-brand-gradient w-full">
                    {submitting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Envoi…
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="h-4 w-4 mr-2" /> J'ai payé
                      </>
                    )}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
