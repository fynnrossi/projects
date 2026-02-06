import type { ReputationScore } from '../../types';
import { getTierInfo } from '../../engine/reputation';
import './ReputationBadge.css';

interface Props {
  reputation: ReputationScore;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  onClick?: (e: React.MouseEvent) => void;
}

export default function ReputationBadge({ reputation, size = 'md', showLabel = false, onClick }: Props) {
  const tier = getTierInfo(reputation.tier);

  return (
    <button
      className={`rep-badge rep-badge--${size} rep-badge--${reputation.tier}`}
      onClick={onClick}
      title={`${tier.label} — ${reputation.overall}/100`}
      style={{ '--tier-color': tier.color } as React.CSSProperties}
    >
      <span className="rep-badge__icon">{tier.icon}</span>
      {showLabel && (
        <span className="rep-badge__label">{tier.label}</span>
      )}
    </button>
  );
}
