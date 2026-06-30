import { useEffect, useState } from 'react';
import { Download, X, Share, Plus } from 'lucide-react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISS_KEY = 'ec_pwa_install_dismissed';

/** App déjà lancée en mode installé (écran d'accueil) ? Inutile de proposer l'install. */
function isStandalone() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    // iOS Safari expose `navigator.standalone` (non typé).
    (navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

/** Safari iOS/iPadOS : pas d'`beforeinstallprompt`, install manuelle via le menu Partager. */
function isIosSafari() {
  const ua = navigator.userAgent;
  const iOS =
    /iPad|iPhone|iPod/.test(ua) ||
    // iPadOS se présente comme un Mac mais reste tactile.
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const webkit = /WebKit/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  return iOS && webkit;
}

/** Invite discrète à installer la PWA (bouton natif Android/Chrome, notice manuelle iOS). */
export default function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [showIos, setShowIos] = useState(false);
  const [hidden, setHidden] = useState(() => localStorage.getItem(DISMISS_KEY) === '1');

  useEffect(() => {
    if (isStandalone()) return;
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    window.addEventListener('beforeinstallprompt', handler);
    // iOS ne déclenchera jamais l'évènement : on affiche directement la notice.
    if (isIosSafari()) setShowIos(true);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  if (hidden || (!deferred && !showIos)) return null;

  const dismiss = () => {
    setHidden(true);
    localStorage.setItem(DISMISS_KEY, '1');
  };

  // iOS : pas de prompt natif, on guide vers « Partager → Sur l'écran d'accueil ».
  if (!deferred && showIos) {
    return (
      <div className="fixed bottom-4 inset-x-4 z-50 flex items-start gap-3 rounded-2xl bg-white shadow-lg border border-slate-200 px-4 py-3 sm:left-4 sm:right-auto sm:max-w-xs">
        <Download className="w-5 h-5 text-blue-700 shrink-0 mt-0.5" />
        <p className="text-sm text-slate-700 leading-snug">
          Installez EmploiCentral : appuyez sur{' '}
          <Share className="inline w-4 h-4 -mt-0.5 text-blue-700" /> puis
          <span className="font-medium"> « Sur l'écran d'accueil »</span>{' '}
          <Plus className="inline w-3.5 h-3.5 -mt-0.5" />.
        </p>
        <button
          onClick={dismiss}
          aria-label="Fermer"
          className="p-1 text-slate-400 hover:text-slate-600 shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  const install = async () => {
    if (!deferred) return;
    await deferred.prompt();
    await deferred.userChoice;
    setDeferred(null);
  };

  return (
    <div className="fixed bottom-4 left-4 z-50 flex items-center gap-2 rounded-full bg-white shadow-lg border border-slate-200 pl-4 pr-2 py-2">
      <span className="text-sm text-slate-700 hidden sm:inline">Installer l'application</span>
      <button
        onClick={install}
        className="inline-flex items-center gap-1.5 rounded-full bg-brand-gradient text-white text-sm font-medium px-3 py-1.5"
      >
        <Download className="w-4 h-4" /> Installer
      </button>
      <button
        onClick={dismiss}
        aria-label="Plus tard"
        className="p-1 text-slate-400 hover:text-slate-600"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
