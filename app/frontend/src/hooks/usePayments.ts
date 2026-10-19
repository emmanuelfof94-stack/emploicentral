import { useQuery } from '@tanstack/react-query';
import { client } from '../lib/api';

// Paiement automatique Wave Checkout (voir backend routers/payments.py).

export type WaveCheckoutStatus = 'pending' | 'paid' | 'failed' | 'expired';

export interface WaveCheckoutState {
  checkout_id: number;
  slug: string;
  status: WaveCheckoutStatus;
}

/** Crée une session Wave et renvoie l'URL de paiement vers laquelle rediriger. */
export async function startWaveCheckout(slug: string): Promise<string> {
  const res = await client.apiCall.invoke({
    url: '/api/v1/payments/wave/checkout',
    method: 'POST',
    data: { slug },
  });
  const body = (res?.data ?? res) as { launch_url: string };
  return body.launch_url;
}

/** Suit une tentative de paiement au retour de Wave, jusqu'à ce qu'elle soit tranchée. */
export function useWaveCheckout(checkoutId?: number) {
  return useQuery({
    queryKey: ['wave_checkout', checkoutId],
    enabled: !!checkoutId,
    staleTime: 0,
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? 3_000 : false),
    queryFn: async (): Promise<WaveCheckoutState> => {
      const res = await client.apiCall.invoke({
        url: `/api/v1/payments/wave/checkout/${checkoutId}`,
        method: 'GET',
      });
      return (res?.data ?? res) as WaveCheckoutState;
    },
  });
}
