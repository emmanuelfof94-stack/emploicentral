import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { BellRing, Loader2 } from 'lucide-react';
import { usePush, isIosBrowserTab } from '../hooks/usePush';

/** Ligne « Notifications sur cet appareil » (canal push des alertes emploi). */
export default function PushToggle() {
  const { state, busy, enable, disable, sendTest } = usePush();

  // Serveur sans clés VAPID : on n'expose pas une option qui ne marcherait pas.
  if (state === 'unconfigured') return null;

  const onChange = async (checked: boolean) => {
    try {
      if (checked) {
        await enable();
      } else {
        await disable();
        toast.success('Notifications désactivées sur cet appareil');
      }
    } catch {
      toast.error("Impossible d'activer les notifications sur ce navigateur.");
    }
  };

  const test = async () => {
    try {
      await sendTest();
      toast.success('Notification de test envoyée');
    } catch {
      toast.error("La notification de test n'a pas pu être envoyée.");
    }
  };

  const hint =
    state === 'unsupported'
      ? isIosBrowserTab()
        ? "Sur iPhone : ajoutez d'abord EmploiCentral à l'écran d'accueil (Partager → Sur l'écran d'accueil), puis activez ici depuis l'appli."
        : 'Ce navigateur ne prend pas en charge les notifications.'
      : state === 'denied'
        ? 'Notifications bloquées pour ce site : autorisez-les dans les réglages du navigateur.'
        : null;

  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm text-slate-600">
          <BellRing className="w-4 h-4 text-violet-600" />
          Notifications sur cet appareil
          {busy && <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" />}
        </span>
        <Switch
          checked={state === 'on'}
          disabled={busy || state === 'loading' || state === 'unsupported' || state === 'denied'}
          onCheckedChange={onChange}
          aria-label="Notifications push sur cet appareil"
        />
      </div>
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
      {state === 'on' && (
        <button type="button" onClick={test} className="text-xs text-violet-700 hover:underline mt-1">
          Envoyer une notification de test
        </button>
      )}
    </div>
  );
}
