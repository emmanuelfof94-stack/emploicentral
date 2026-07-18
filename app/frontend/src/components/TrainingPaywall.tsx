import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { CheckCircle2, Clock, Loader2, Lock, Smartphone, Infinity as InfinityIcon } from 'lucide-react';
import { useTrainingQuota, useTrainingAccessActions } from '../hooks/useApi';

/**
 * Modale de déblocage « accès illimité aux formations ».
 * S'affiche quand le candidat a épuisé ses 5 accès gratuits (parcours IA +
 * déblocages du catalogue). Paiement mobile money déclaré → validé par un admin.
 */
export default function TrainingPaywall({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { data: quota } = useTrainingQuota(open);
  const { purchaseUnlimited } = useTrainingAccessActions();
  const [ref, setRef] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const pending = quota?.purchase_status === 'pending';

  const onSubmit = async () => {
    if (!ref.trim()) {
      toast.error('Indiquez le numéro / la référence utilisé pour payer.');
      return;
    }
    setSubmitting(true);
    try {
      await purchaseUnlimited(ref.trim());
      toast.success('Demande envoyée ! Nous validons votre paiement sous peu.');
    } catch {
      toast.error("Échec de l'envoi. Réessayez.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-primary" /> Accès aux formations épuisé
          </DialogTitle>
          <DialogDescription>
            Vous avez utilisé vos <b>{quota?.limit ?? 5} accès gratuits</b> aux formations
            (parcours IA + déblocages du catalogue). Débloquez l'accès illimité à vie pour continuer.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 flex items-center gap-3">
          <InfinityIcon className="h-6 w-6 text-primary shrink-0" />
          <div>
            <p className="text-2xl font-bold text-primary leading-none">{quota?.price ?? '2 000 FCFA'}</p>
            <p className="text-xs text-muted-foreground mt-1">
              Paiement unique · accès illimité à vie à toutes les formations
            </p>
          </div>
        </div>

        {pending ? (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-amber-800 flex gap-2">
            <Clock className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Paiement en cours de vérification</p>
              <p className="text-sm mt-1">
                Nous validons votre paiement. Vous recevrez une notification dès que l'accès sera débloqué.
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
                  Envoyez <b>{quota?.price ?? '2 000 FCFA'}</b> par <b>Wave</b> ou <b>Orange Money</b> au numéro :
                </li>
                <li className="list-none -ml-5">
                  <span className="font-mono text-base font-bold text-foreground">
                    {quota?.payment_number ?? '+225 07 49 10 90 13'}
                  </span>
                </li>
                <li>Notez le numéro que vous avez utilisé pour payer.</li>
                <li>Saisissez-le ci-dessous et cliquez « J'ai payé ».</li>
              </ol>
            </div>

            {quota?.purchase_status === 'rejected' && (
              <p className="text-sm text-destructive">
                Votre précédent paiement n'a pas été confirmé. Vérifiez et soumettez à nouveau.
              </p>
            )}

            <div className="space-y-2">
              <Label htmlFor="pay-ref">Votre numéro / référence de paiement</Label>
              <Input
                id="pay-ref"
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
      </DialogContent>
    </Dialog>
  );
}
