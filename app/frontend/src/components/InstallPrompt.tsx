import { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISS_KEY = 'ec_pwa_install_dismissed';

/** Invite discrète à installer la PWA, déclenchée par `beforeinstallprompt`. */
export default function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [hidden, setHidden] = useState(() => localStorage.getItem(DISMISS_KEY) === '1');

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  if (!deferred || hidden) return null;

  const install = async () => {
    await deferred.prompt();
    await deferred.userChoice;
    setDeferred(null);
  };

  const dismiss = () => {
    setHidden(true);
    localStorage.setItem(DISMISS_KEY, '1');
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
