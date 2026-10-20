import { client } from '../lib/api';

// Assistant de recherche d'emploi en conversation (backend routers/assistant.py).

export interface AssistantTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface AssistantJob {
  id: number;
  title: string;
  company: string;
  location?: string | null;
  contract_type?: string | null;
  sector?: string | null;
}

export interface AssistantReply {
  reply: string;
  jobs: AssistantJob[];
  ai: boolean;
  remaining_today: number;
}

/** Envoie l'historique (20 derniers messages max) et renvoie la réponse de l'assistant. */
export async function askAssistant(messages: AssistantTurn[]): Promise<AssistantReply> {
  const res = await client.apiCall.invoke({
    url: '/api/v1/assistant/chat',
    method: 'POST',
    data: { messages: messages.slice(-20) },
  });
  return (res?.data ?? res) as AssistantReply;
}
