import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useWaveCheckout } from '../hooks/usePayments';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';

/** Où renvoyer le candidat une fois le produit débloqué. */
function productLink(slug: string): { to: string; label: string } {
  if (slug === 'formations-illimite') return { to: '/trainings', label: 'Aller aux formations' };
  return { to: `/cours/${slug}`, label: 'Accéder au cours' };
}

/** Retour de Wave : on attend la confirmation du paiement (relue côté serveur chez Wave). */
export default function PaymentReturn() {
  const [params] = useSearchParams();
  const checkoutId = Number(params.get('checkout')) || undefined;
  const { data, isLoading, isError } = useWaveCheckout(checkoutId);
  const status = data?.status;
  const target = data ? productLink(data.slug) : null;

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-md mx-auto px-4 py-16">
        <Card className="border-slate-200/70 shadow-sm">
          <CardContent className="p-6 text-center space-y-4">
            {!checkoutId || isError ? (
              <>
                <XCircle className="w-10 h-10 text-slate-400 mx-auto" />
                <p className="font-semibold text-slate-900">Paiement introuvable</p>
                <p className="text-sm text-slate-500">
                  Si vous avez été débité, votre accès sera débloqué automatiquement d&apos;ici quelques
                  minutes. Sinon, contactez-nous.
                </p>
              </>
            ) : isLoading || status === 'pending' ? (
              <>
                <Loader2 className="w-10 h-10 text-blue-600 animate-spin mx-auto" />
                <p className="font-semibold text-slate-900">Confirmation du paiement…</p>
                <p className="text-sm text-slate-500">
                  Nous attendons la confirmation de Wave. Gardez cette page ouverte, cela prend
                  quelques secondes.
                </p>
              </>
            ) : status === 'paid' ? (
              <>
                <CheckCircle2 className="w-10 h-10 text-green-600 mx-auto" />
                <p className="font-semibold text-slate-900">Paiement reçu, accès débloqué !</p>
                {target && (
                  <Link to={target.to} className="inline-block">
                    <Button className="bg-brand-gradient hover:opacity-95">{target.label}</Button>
                  </Link>
                )}
              </>
            ) : (
              <>
                <XCircle className="w-10 h-10 text-red-500 mx-auto" />
                <p className="font-semibold text-slate-900">
                  {status === 'expired' ? 'Session de paiement expirée' : 'Paiement non abouti'}
                </p>
                <p className="text-sm text-slate-500">
                  Le paiement n&apos;a pas été confirmé par Wave. Vous pouvez réessayer ; si vous avez
                  quand même été débité, contactez-nous.
                </p>
                {target && (
                  <Link to={target.to} className="inline-block">
                    <Button variant="outline">Réessayer</Button>
                  </Link>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
