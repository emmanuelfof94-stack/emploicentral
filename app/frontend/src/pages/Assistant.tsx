import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import Markdown from 'markdown-to-jsx';
import Navbar from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';
import { askAssistant, type AssistantJob, type AssistantTurn } from '../hooks/useAssistant';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Sparkles, Send, Loader2, MapPin, Building2, Briefcase, RotateCcw, ArrowRight } from 'lucide-react';

type Message = AssistantTurn & { jobs?: AssistantJob[] };

const SUGGESTIONS = [
  'Quelles offres correspondent à mon CV ?',
  'Je cherche un stage à Abidjan',
  'Des postes de comptable en CDI',
  'Des offres dans le BTP à Bouaké',
];

const WELCOME: Message = {
  role: 'assistant',
  content:
    "Bonjour ! Je suis votre assistant emploi. Dites-moi quel poste vous cherchez, où et avec quel type de contrat : je vous propose les offres actives qui vous correspondent le mieux.",
};

// Historique conservé dans ce navigateur uniquement (confort), jamais indispensable.
function storageKey(userId?: string | number) {
  return `assistant_history_v1:${userId ?? 'anon'}`;
}
function loadHistory(key: string): Message[] {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? (JSON.parse(raw) as Message[]) : null;
    return Array.isArray(parsed) && parsed.length ? parsed : [WELCOME];
  } catch {
    return [WELCOME];
  }
}
function saveHistory(key: string, messages: Message[]) {
  try {
    localStorage.setItem(key, JSON.stringify(messages.slice(-30)));
  } catch {
    /* stockage indisponible (navigation privée…) : sans conséquence */
  }
}

/** Les références [#123] deviennent des liens vers l'offre dans l'espace candidat. */
function linkify(text: string) {
  return text.replace(/\[#(\d+)\]/g, '[(voir l’offre)](/jobs?job=$1)');
}

function errorDetail(e: unknown): string {
  const anyE = e as { response?: { data?: { detail?: string } }; data?: { detail?: string } };
  return anyE?.response?.data?.detail || anyE?.data?.detail || "L'assistant est momentanément indisponible.";
}

export default function Assistant() {
  const { user } = useAuth();
  const key = storageKey(user?.id);
  const [messages, setMessages] = useState<Message[]>(() => loadHistory(key));
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    saveHistory(key, messages);
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [key, messages]);

  const send = async (text: string) => {
    const content = text.trim();
    if (!content || sending) return;
    const next: Message[] = [...messages, { role: 'user', content }];
    setMessages(next);
    setInput('');
    setSending(true);
    try {
      // Le message d'accueil local n'est pas envoyé au serveur.
      const history = next.filter((m) => m !== WELCOME && m.content !== WELCOME.content)
        .map(({ role, content: c }) => ({ role, content: c }));
      const res = await askAssistant(history);
      setMessages([...next, { role: 'assistant', content: res.reply, jobs: res.jobs }]);
    } catch (e) {
      toast.error(errorDetail(e));
      setMessages(messages); // on rend la main sans perdre la saisie
      setInput(content);
    } finally {
      setSending(false);
    }
  };

  const reset = () => setMessages([WELCOME]);

  return (
    <div className="min-h-screen app-surface flex flex-col">
      <Navbar />
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 py-6 flex flex-col">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h1 className="font-display text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-blue-600" /> Assistant emploi
            </h1>
            <p className="text-sm text-slate-500">Décrivez ce que vous cherchez, je trouve les offres pour vous.</p>
          </div>
          {messages.length > 1 && (
            <Button variant="ghost" size="sm" onClick={reset} disabled={sending} aria-label="Nouvelle conversation">
              <RotateCcw className="w-4 h-4 sm:mr-1.5" />
              <span className="hidden sm:inline">Nouvelle conversation</span>
            </Button>
          )}
        </div>

        <div className="flex-1 space-y-4 pb-4" aria-live="polite">
          {messages.map((m, idx) => (
            <div key={idx} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div className={m.role === 'user' ? 'max-w-[85%]' : 'max-w-[92%] min-w-0'}>
                <div
                  className={
                    m.role === 'user'
                      ? 'rounded-2xl rounded-br-sm bg-brand-gradient text-white px-4 py-2.5 text-sm whitespace-pre-line'
                      : 'rounded-2xl rounded-bl-sm bg-white border border-slate-200/80 shadow-sm px-4 py-3 text-sm text-slate-700 prose prose-sm max-w-none prose-p:my-1.5 prose-ul:my-1.5'
                  }
                >
                  {m.role === 'user' ? (
                    m.content
                  ) : (
                    <Markdown
                      options={{
                        overrides: {
                          a: {
                            component: ({ href = '', children }: { href?: string; children: React.ReactNode }) =>
                              href.startsWith('/') ? (
                                <Link to={href} className="text-blue-600 font-medium">{children}</Link>
                              ) : (
                                <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
                              ),
                          },
                        },
                      }}
                    >
                      {linkify(m.content)}
                    </Markdown>
                  )}
                </div>
                {m.jobs && m.jobs.length > 0 && (
                  <div className="mt-2 grid gap-2 min-w-0">
                    {m.jobs.map((j) => (
                      <Link key={j.id} to={`/jobs?job=${j.id}`} className="block min-w-0">
                        <Card className="border-slate-200/70 shadow-sm card-lift">
                          <CardContent className="p-3 flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <p className="font-semibold text-slate-900 text-sm truncate">{j.title}</p>
                              <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5 text-xs text-slate-500">
                                <span className="flex items-center gap-1"><Building2 className="w-3.5 h-3.5" />{j.company}</span>
                                {j.location && (
                                  <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" />{j.location}</span>
                                )}
                                {j.contract_type && j.contract_type !== 'Non précisé' && (
                                  <span className="flex items-center gap-1"><Briefcase className="w-3.5 h-3.5" />{j.contract_type}</span>
                                )}
                              </div>
                            </div>
                            <ArrowRight className="w-4 h-4 text-blue-600 shrink-0" />
                          </CardContent>
                        </Card>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm bg-white border border-slate-200/80 px-4 py-3 text-sm text-slate-500 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Je cherche les meilleures offres…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {messages.length <= 1 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="text-xs sm:text-sm rounded-full border border-blue-200 bg-blue-50/70 text-blue-700 px-3 py-1.5 hover:bg-blue-100"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="sticky bottom-0 bg-gradient-to-t from-white via-white to-transparent pt-2 pb-3"
        >
          <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white shadow-sm p-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ex. un poste de comptable en CDI à Abidjan"
              rows={1}
              maxLength={2000}
              className="min-h-[44px] max-h-40 resize-none border-0 shadow-none focus-visible:ring-0"
              aria-label="Votre message à l'assistant"
            />
            <Button type="submit" disabled={sending || !input.trim()} className="bg-brand-gradient h-10 w-10 p-0 shrink-0" aria-label="Envoyer">
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          </div>
          <p className="text-[11px] text-slate-400 mt-1.5 text-center">
            L&apos;assistant ne propose que des offres réellement publiées sur EmploiCentral. Vérifiez toujours les détails sur l&apos;offre.
          </p>
        </form>
      </main>
    </div>
  );
}
