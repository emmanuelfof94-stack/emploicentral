// Configuration WhatsApp d'EmploiCentral.
//
// Renseigne ici le numéro WhatsApp du support au format INTERNATIONAL, sans '+',
// sans espaces (ex. Côte d'Ivoire : "2250700000000"). Laisser vide ('') masque
// automatiquement le bouton de contact flottant.
export const SUPPORT_WHATSAPP = '';

/** Lien wa.me pour CONTACTER le support EmploiCentral (message prérempli). */
export function waContactUrl(
  text = "Bonjour, j'ai une question sur EmploiCentral."
): string {
  return `https://wa.me/${SUPPORT_WHATSAPP}?text=${encodeURIComponent(text)}`;
}

/** Lien wa.me pour PARTAGER un texte/offre (l'utilisateur choisit le destinataire). */
export function waShareUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}
