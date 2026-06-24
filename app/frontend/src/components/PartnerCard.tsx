import { Badge } from '@/components/ui/badge';
import { Building2, ExternalLink, Mail, Phone, MapPin } from 'lucide-react';
import type { TrainingPartner } from '../hooks/useApi';

function PricingBadge({ pricing }: { pricing?: string }) {
  const free = pricing === 'free';
  return (
    <Badge
      variant="outline"
      className={
        free
          ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
          : 'border-amber-300 bg-amber-50 text-amber-700'
      }
    >
      {free ? 'Gratuit' : 'Payant'}
    </Badge>
  );
}

/** Carte d'un organisme partenaire. `compact` réduit le rendu pour les suggestions. */
export default function PartnerCard({
  partner,
  compact = false,
}: {
  partner: TrainingPartner;
  compact?: boolean;
}) {
  const domains = (partner.domains || '')
    .split(',')
    .map((d) => d.trim())
    .filter(Boolean);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start gap-3">
        <div className="shrink-0">
          {partner.logo_url ? (
            <img
              src={partner.logo_url}
              alt={partner.name}
              className="w-10 h-10 rounded-lg object-cover border border-slate-100"
            />
          ) : (
            <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-blue-600" />
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-slate-900 truncate">{partner.name}</h3>
            <PricingBadge pricing={partner.pricing} />
          </div>
          {partner.description && (
            <p className={`text-sm text-slate-600 mt-1 ${compact ? 'line-clamp-2' : ''}`}>
              {partner.description}
            </p>
          )}

          {!compact && domains.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {domains.slice(0, 8).map((d) => (
                <span
                  key={d}
                  className="text-[11px] rounded-full bg-slate-100 text-slate-600 px-2 py-0.5"
                >
                  {d}
                </span>
              ))}
            </div>
          )}

          {!compact && (partner.location || partner.contact_email || partner.contact_phone) && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
              {partner.location && (
                <span className="inline-flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" /> {partner.location}
                </span>
              )}
              {partner.contact_email && (
                <a
                  href={`mailto:${partner.contact_email}`}
                  className="inline-flex items-center gap-1 hover:text-blue-600"
                >
                  <Mail className="w-3.5 h-3.5" /> {partner.contact_email}
                </a>
              )}
              {partner.contact_phone && (
                <a
                  href={`tel:${partner.contact_phone}`}
                  className="inline-flex items-center gap-1 hover:text-blue-600"
                >
                  <Phone className="w-3.5 h-3.5" /> {partner.contact_phone}
                </a>
              )}
            </div>
          )}

          <a
            href={partner.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 mt-3 text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Visiter le site <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
