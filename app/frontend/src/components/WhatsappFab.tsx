import { SUPPORT_WHATSAPP, waContactUrl } from '../lib/whatsapp';
import { MessageCircle } from 'lucide-react';

/**
 * Bouton flottant « Contacter EmploiCentral sur WhatsApp ».
 * Ne s'affiche que si un numéro support est configuré dans `lib/whatsapp.ts`.
 */
export default function WhatsappFab() {
  if (!SUPPORT_WHATSAPP) return null;
  return (
    <a
      href={waContactUrl()}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Contacter EmploiCentral sur WhatsApp"
      className="fixed bottom-4 right-4 z-50 inline-flex items-center gap-2 rounded-full bg-[#25D366] text-white shadow-lg px-4 py-3 hover:brightness-95 transition"
    >
      <MessageCircle className="w-5 h-5" />
      <span className="text-sm font-medium hidden sm:inline">Besoin d'aide ?</span>
    </a>
  );
}
