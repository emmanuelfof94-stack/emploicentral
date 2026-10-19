import Markdown from 'markdown-to-jsx';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Mic, Sparkles } from 'lucide-react';
import type { JobDocuments } from './useJobDocuments';

/** Coach d'entretien : résultat. */
export default function InterviewPrepDialog({ prep }: { prep: JobDocuments['prep'] }) {
  return (
    <Dialog open={prep.open} onOpenChange={prep.setOpen}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mic className="w-5 h-5 text-violet-600" />
            Préparation à l'entretien
            {prep.ai && (
              <span className="inline-flex items-center gap-1 text-xs font-normal text-violet-600">
                <Sparkles className="w-3.5 h-3.5" /> IA
              </span>
            )}
          </DialogTitle>
        </DialogHeader>
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <Markdown>{prep.content}</Markdown>
        </div>
      </DialogContent>
    </Dialog>
  );
}
