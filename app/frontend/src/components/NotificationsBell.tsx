import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useNotifications, useMarkNotificationsRead } from '../hooks/useApi';
import { useAuth } from '../contexts/AuthContext';

/** Short French relative time, e.g. "il y a 2 h", "à l'instant". */
function timeAgo(iso?: string): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return "à l'instant";
  const m = Math.floor(s / 60);
  if (m < 60) return `il y a ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `il y a ${d} j`;
  return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

export default function NotificationsBell() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const { data } = useNotifications(!!user);
  const markRead = useMarkNotificationsRead();

  const items = data?.items ?? [];
  const unread = data?.unread ?? 0;

  // Mark everything read as soon as the panel is opened (standard bell UX).
  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (next && unread > 0) {
      void markRead();
    }
  };

  const goToOffer = () => {
    setOpen(false);
    navigate('/jobs');
  };

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Notifications"
          className="relative p-2 rounded-md text-slate-600 hover:bg-slate-100 transition-colors"
        >
          <Bell className="w-5 h-5" />
          {unread > 0 && (
            <span className="absolute top-1 right-1 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold leading-none">
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-semibold text-slate-900">Notifications</span>
          {items.length > 0 && (
            <button
              type="button"
              onClick={() => void markRead()}
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-blue-600"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              Tout marquer lu
            </button>
          )}
        </div>

        {items.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-400">
            <Bell className="w-6 h-6 mx-auto mb-2 opacity-40" />
            Aucune notification pour l&apos;instant.
            <br />
            Vos meilleures offres apparaîtront ici.
          </div>
        ) : (
          <ScrollArea className="max-h-96">
            <ul className="divide-y divide-slate-100">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={goToOffer}
                    className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors ${
                      n.is_read ? '' : 'bg-blue-50/60'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {!n.is_read && (
                        <span className="mt-1.5 w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                      )}
                      <div className={`min-w-0 ${n.is_read ? 'pl-4' : ''}`}>
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {n.title}
                        </p>
                        {n.body && (
                          <p className="text-xs text-slate-500 truncate">{n.body}</p>
                        )}
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          {timeAgo(n.created_at)}
                        </p>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
      </PopoverContent>
    </Popover>
  );
}
