import { Component, type ReactNode } from 'react';

/**
 * Rattrape les erreurs de rendu — en particulier l'échec de chargement d'un
 * chunk lazy (`import()`), symptôme classique après un redéploiement : le SPA
 * chargé AVANT le déploiement garde en mémoire d'anciens hashs de chunks qui
 * n'existent plus côté serveur (404). Sans ce garde-fou, l'échec démontait tout
 * l'arbre React → page blanche.
 *
 * Stratégie : à une erreur de chunk, on recharge la page (le service worker sert
 * l'index frais → bons hashs → auto-guérison). Un horodatage en session borne les
 * rechargements à un seul par fenêtre de 10 s : un futur déploiement (bien plus
 * tard) guérit toujours, mais une erreur qui PERSISTE après reload n'entraîne pas
 * de boucle — on affiche alors un repli lisible avec un bouton manuel.
 */
const RELOAD_TS = 'ec_chunk_reload_ts';
const COOLDOWN_MS = 10_000;

function isChunkError(error: unknown): boolean {
  const msg = (error instanceof Error ? error.message : String(error || '')).toLowerCase();
  const name = error instanceof Error ? error.name.toLowerCase() : '';
  return (
    name === 'chunkloaderror' ||
    msg.includes('loading chunk') ||
    msg.includes('dynamically imported module') ||
    msg.includes('importing a module script failed') ||
    msg.includes('failed to fetch dynamically imported module') ||
    msg.includes('error loading dynamically imported module')
  );
}

function reloadedRecently(): boolean {
  if (typeof sessionStorage === 'undefined') return false;
  const last = Number(sessionStorage.getItem(RELOAD_TS) || 0);
  return Number.isFinite(last) && Date.now() - last < COOLDOWN_MS;
}

type Props = { children: ReactNode };
type State = { phase: 'ok' | 'reloading' | 'failed' };

export default class ChunkErrorBoundary extends Component<Props, State> {
  state: State = { phase: 'ok' };

  static getDerivedStateFromError(error: unknown): State {
    // Pur : on ne fait que calculer le prochain état. On tente une guérison
    // uniquement pour une erreur de chunk qu'on n'a pas déjà tenté de recharger
    // à l'instant. Le rechargement (effet de bord) est fait dans componentDidCatch.
    if (isChunkError(error) && !reloadedRecently()) return { phase: 'reloading' };
    return { phase: 'failed' };
  }

  componentDidCatch() {
    if (this.state.phase === 'reloading' && typeof window !== 'undefined') {
      try {
        sessionStorage.setItem(RELOAD_TS, String(Date.now()));
      } catch {
        /* sessionStorage indisponible : on recharge quand même une fois. */
      }
      window.location.reload();
    }
  }

  render() {
    if (this.state.phase === 'ok') return this.props.children;

    if (this.state.phase === 'reloading') {
      return (
        <div className="flex min-h-[60vh] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
        </div>
      );
    }

    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 px-6 text-center">
        <h2 className="text-lg font-semibold">Une nouvelle version est disponible</h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          L'application a été mise à jour. Recharge la page pour continuer.
        </p>
        <button
          onClick={() => {
            try {
              sessionStorage.removeItem(RELOAD_TS);
            } catch {
              /* ignore */
            }
            window.location.reload();
          }}
          className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Mettre à jour
        </button>
      </div>
    );
  }
}
