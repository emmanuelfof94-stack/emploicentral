interface BrandLogoProps {
  /** Affiche la signature « propulsé par l'IA » sous le nom. */
  tagline?: boolean;
  /** Taille globale du bloc logo. */
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const MARK = {
  sm: 'w-8 h-8 text-sm rounded-lg',
  md: 'w-9 h-9 text-base rounded-xl',
  lg: 'w-11 h-11 text-lg rounded-2xl',
};
const NAME = {
  sm: 'text-lg',
  md: 'text-xl',
  lg: 'text-2xl',
};

/**
 * Identité de marque unifiée : monogramme « EC » (assorti à l'icône PWA) +
 * « EmploiCentral » + signature « propulsé par l'IA ». Remplace l'ancien
 * « JobMatch AI » affiché de façon incohérente selon les écrans.
 */
export default function BrandLogo({ tagline = false, size = 'md', className = '' }: BrandLogoProps) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div
        className={`bg-warm-gradient flex items-center justify-center font-display font-extrabold text-white shadow-sm shadow-terracotta-500/30 ${MARK[size]}`}
      >
        EC
      </div>
      <div className="flex flex-col leading-none">
        <span className={`font-display font-extrabold tracking-tight text-slate-900 ${NAME[size]}`}>
          Emploi<span className="text-terracotta-600">Central</span>
        </span>
        {tagline && (
          <span className="text-[11px] font-medium text-slate-400 mt-0.5">propulsé par l&apos;IA</span>
        )}
      </div>
    </div>
  );
}
