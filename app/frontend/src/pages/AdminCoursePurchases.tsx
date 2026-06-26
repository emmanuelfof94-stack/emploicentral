import Navbar from '../components/Navbar';
import { useAdminPurchases, useAdminPurchaseActions, type AdminPurchase } from '../hooks/useApi';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Loader2, CheckCircle2, XCircle, CreditCard } from 'lucide-react';

const STATUS: Record<string, { label: string; cls: string }> = {
  pending: { label: 'En attente', cls: 'bg-amber-100 text-amber-800' },
  paid: { label: 'Validé', cls: 'bg-emerald-100 text-emerald-800' },
  rejected: { label: 'Rejeté', cls: 'bg-red-100 text-red-700' },
};

export default function AdminCoursePurchases() {
  const { data: purchases, isLoading } = useAdminPurchases();
  const { validate, reject } = useAdminPurchaseActions();

  const run = async (fn: (id: number) => Promise<void>, id: number, ok: string) => {
    try {
      await fn(id);
      toast.success(ok);
    } catch {
      toast.error('Action impossible.');
    }
  };

  const pending = (purchases ?? []).filter((p) => p.status === 'pending');

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <CreditCard className="h-6 w-6 text-primary" /> Achats de cours
          </h1>
          <p className="text-muted-foreground mt-1">
            Valide ou rejette les demandes de paiement (mobile money) des cours payants.
            {pending.length > 0 && (
              <span className="ml-1 font-medium text-amber-700">
                {pending.length} en attente.
              </span>
            )}
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
          </div>
        ) : !purchases || purchases.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              Aucune demande d'achat pour l'instant.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {purchases.map((p: AdminPurchase) => {
              const st = STATUS[p.status] ?? { label: p.status, cls: 'bg-slate-100 text-slate-700' };
              return (
                <Card key={p.id} className="card-lift">
                  <CardContent className="py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold">{p.course_title}</span>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${st.cls}`}>
                            {st.label}
                          </span>
                          {p.amount && (
                            <span className="text-xs text-muted-foreground">{p.amount}</span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          Candidat : <b>{p.user_email || p.user_id}</b>
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Référence paiement : <b className="font-mono">{p.payment_ref || '—'}</b>
                          {p.created_at && (
                            <span className="ml-2">
                              · {new Date(p.created_at).toLocaleString('fr-FR')}
                            </span>
                          )}
                        </p>
                      </div>
                      {p.status === 'pending' && (
                        <div className="flex items-center gap-2 shrink-0">
                          <Button
                            size="sm"
                            onClick={() => run(validate, p.id, 'Accès validé ✅')}
                            className="bg-emerald-600 hover:bg-emerald-700"
                          >
                            <CheckCircle2 className="h-4 w-4 mr-1" /> Valider
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => run(reject, p.id, 'Demande rejetée')}
                            className="text-destructive hover:text-destructive"
                          >
                            <XCircle className="h-4 w-4 mr-1" /> Rejeter
                          </Button>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
