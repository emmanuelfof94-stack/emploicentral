import { useState } from 'react';
import Navbar from '../components/Navbar';
import { usePendingPostings, useModerationActions } from '../hooks/useApi';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { ShieldCheck, Loader2, Check, X, MapPin, Mail } from 'lucide-react';

export default function AdminModeration() {
  const { data: pending, isLoading } = usePendingPostings();
  const { approve, reject } = useModerationActions();
  const [busy, setBusy] = useState<number | null>(null);

  const onApprove = async (postingId: number) => {
    setBusy(postingId);
    try {
      await approve(postingId);
      toast.success('Offre approuvée et mise en ligne.');
    } catch {
      toast.error('Action impossible.');
    } finally {
      setBusy(null);
    }
  };

  const onReject = async (postingId: number) => {
    const reason = window.prompt('Motif du refus (facultatif, visible par le recruteur) :') ?? '';
    setBusy(postingId);
    try {
      await reject(postingId, reason);
      toast.success('Offre refusée.');
    } catch {
      toast.error('Action impossible.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-primary" />
            Modération des offres {pending ? `(${pending.length})` : ''}
          </h1>
          <p className="text-muted-foreground mt-1">
            Offres soumises par les recruteurs, en attente de validation avant publication.
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
          </div>
        ) : !pending || pending.length === 0 ? (
          <p className="text-muted-foreground">Aucune offre en attente. 🎉</p>
        ) : (
          <div className="space-y-3">
            {pending.map((p) => (
              <Card key={p.posting_id} className="card-lift">
                <CardContent className="py-4 space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <span className="font-semibold text-slate-900">{p.title}</span>
                      <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-slate-500">
                        {p.company && <Badge variant="secondary">{p.company}</Badge>}
                        {p.location && (
                          <span className="inline-flex items-center gap-1">
                            <MapPin className="w-3 h-3" /> {p.location}
                          </span>
                        )}
                        {p.sector && <span>{p.sector}</span>}
                        {p.recruiter_email && (
                          <span className="inline-flex items-center gap-1">
                            <Mail className="w-3 h-3" /> {p.recruiter_email}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        size="sm"
                        onClick={() => onApprove(p.posting_id)}
                        disabled={busy === p.posting_id}
                        className="bg-emerald-600 hover:bg-emerald-700"
                      >
                        {busy === p.posting_id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Check className="h-4 w-4 mr-1" />
                        )}
                        Approuver
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onReject(p.posting_id)}
                        disabled={busy === p.posting_id}
                        className="text-red-600 border-red-200 hover:bg-red-50"
                      >
                        <X className="h-4 w-4 mr-1" /> Refuser
                      </Button>
                    </div>
                  </div>
                  {p.description && (
                    <p className="text-sm text-slate-600 line-clamp-3">{p.description}</p>
                  )}
                  {p.requirements && (
                    <p className="text-xs text-slate-500">
                      <span className="font-medium">Exigences :</span> {p.requirements}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
