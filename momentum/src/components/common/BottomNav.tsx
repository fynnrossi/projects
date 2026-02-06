import { useLocation, useNavigate } from 'react-router-dom';
import { Compass, MessageCircle, Heart, User } from 'lucide-react';
import { useAppState } from '../../hooks/useAppState';
import './BottomNav.css';

const tabs = [
  { path: '/discover', icon: Compass, label: 'Discover' },
  { path: '/matches', icon: Heart, label: 'Matches' },
  { path: '/chat', icon: MessageCircle, label: 'Chat', matchPrefix: true },
  { path: '/profile', icon: User, label: 'Profile' },
];

export default function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const { matches, conversations } = useAppState();

  const unreadCount = matches.filter(m => m.hasUnread).length +
    conversations.filter(c => c.messages.some(m => !m.read && m.senderId !== 'user-me')).length;

  const isActive = (tab: typeof tabs[0]) => {
    if (tab.matchPrefix) return location.pathname.startsWith('/chat');
    return location.pathname === tab.path;
  };

  // Don't show on chat detail pages
  if (location.pathname.startsWith('/chat/')) return null;

  return (
    <nav className="bottom-nav">
      {tabs.map(tab => {
        const active = isActive(tab);
        const Icon = tab.icon;
        const showBadge = (tab.path === '/matches' || tab.path === '/chat') && unreadCount > 0;

        return (
          <button
            key={tab.path}
            className={`nav-tab ${active ? 'nav-tab--active' : ''}`}
            onClick={() => {
              if (tab.path === '/chat') {
                navigate('/matches');
              } else {
                navigate(tab.path);
              }
            }}
          >
            <div className="nav-tab__icon-wrap">
              <Icon size={24} strokeWidth={active ? 2.5 : 1.8} />
              {showBadge && <span className="nav-tab__badge" />}
            </div>
            <span className="nav-tab__label">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
