import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search } from 'lucide-react';
import type { JobFilterValues, JobSort } from './jobFilterValues';

function FilterSelect({
  value,
  onChange,
  placeholder,
  allLabel,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  allLabel: string;
  options: string[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="bg-white"><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        <SelectItem value="all">{allLabel}</SelectItem>
        {options.map((o) => (<SelectItem key={o} value={o}>{o}</SelectItem>))}
      </SelectContent>
    </Select>
  );
}

/** Recherche + filtres (secteur, lieu, contrat, source) + bascule de tri. */
export default function JobFilters({
  values,
  onChange,
  sortBy,
  onSortChange,
  sectors,
  locations,
  contractTypes,
  sources,
}: {
  values: JobFilterValues;
  onChange: (v: JobFilterValues) => void;
  sortBy: JobSort;
  onSortChange: (s: JobSort) => void;
  sectors: string[];
  locations: string[];
  contractTypes: string[];
  sources: string[];
}) {
  const set = (patch: Partial<JobFilterValues>) => onChange({ ...values, ...patch });

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 mb-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Rechercher..."
            value={values.search}
            onChange={(e) => set({ search: e.target.value })}
            className="pl-10 bg-white"
          />
        </div>
        <FilterSelect value={values.sector} onChange={(sector) => set({ sector })}
          placeholder="Secteur" allLabel="Tous les secteurs" options={sectors} />
        <FilterSelect value={values.location} onChange={(location) => set({ location })}
          placeholder="Localisation" allLabel="Toutes les localisations" options={locations} />
        <FilterSelect value={values.contract} onChange={(contract) => set({ contract })}
          placeholder="Contrat" allLabel="Tous les types" options={contractTypes} />
        <FilterSelect value={values.source} onChange={(source) => set({ source })}
          placeholder="Source" allLabel="Toutes les sources" options={sources} />
      </div>

      {/* Tri */}
      <div className="flex items-center justify-end gap-2 mb-6">
        <span className="text-xs text-slate-500">Trier :</span>
        <div className="inline-flex rounded-md border border-slate-200 bg-white overflow-hidden text-sm">
          <button
            type="button"
            onClick={() => onSortChange('score')}
            className={`px-3 py-1.5 transition-colors ${
              sortBy === 'score' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            Compatibilité
          </button>
          <button
            type="button"
            onClick={() => onSortChange('recent')}
            className={`px-3 py-1.5 transition-colors border-l border-slate-200 ${
              sortBy === 'recent' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            Plus récentes
          </button>
        </div>
      </div>
    </>
  );
}
