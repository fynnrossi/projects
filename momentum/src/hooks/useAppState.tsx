import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { UserProfile, Match, Conversation, Message } from '../types';
import { currentUser, discoverProfiles, mockMatches, mockConversations } from '../data/profiles';

interface AppContextType {
  currentUser: UserProfile;
  discoverQueue: UserProfile[];
  matches: Match[];
  conversations: Conversation[];
  // Actions
  passProfile: () => void;
  likeProfile: (comment?: string, promptIndex?: number) => void;
  sendMessage: (conversationId: string, content: string) => void;
  getProfile: (userId: string) => UserProfile | undefined;
  getConversation: (matchId: string) => Conversation | undefined;
  currentDiscoverIndex: number;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [discoverQueue] = useState<UserProfile[]>(discoverProfiles);
  const [currentDiscoverIndex, setCurrentDiscoverIndex] = useState(0);
  const [matches, setMatches] = useState<Match[]>(mockMatches);
  const [conversations, setConversations] = useState<Conversation[]>(mockConversations);

  const passProfile = useCallback(() => {
    setCurrentDiscoverIndex(prev => Math.min(prev + 1, discoverQueue.length - 1));
  }, [discoverQueue.length]);

  const likeProfile = useCallback((comment?: string, promptIndex?: number) => {
    const profile = discoverQueue[currentDiscoverIndex];
    if (!profile) return;

    const newMatch: Match = {
      id: `match-new-${Date.now()}`,
      users: [currentUser.id, profile.id],
      status: 'matched',
      createdAt: new Date().toISOString(),
      like: {
        fromUserId: currentUser.id,
        toUserId: profile.id,
        type: comment ? 'comment' : 'like',
        comment,
        targetPromptIndex: promptIndex,
        timestamp: new Date().toISOString(),
      },
      lastActivity: new Date().toISOString(),
      hasUnread: false,
    };

    setMatches(prev => [newMatch, ...prev]);
    setCurrentDiscoverIndex(prev => Math.min(prev + 1, discoverQueue.length - 1));
  }, [currentDiscoverIndex, discoverQueue]);

  const sendMessage = useCallback((conversationId: string, content: string) => {
    const newMessage: Message = {
      id: `msg-${Date.now()}`,
      senderId: currentUser.id,
      content,
      timestamp: new Date().toISOString(),
      read: false,
      type: 'text',
    };

    setConversations(prev =>
      prev.map(c =>
        c.id === conversationId
          ? { ...c, messages: [...c.messages, newMessage], lastMessageAt: newMessage.timestamp }
          : c
      )
    );
  }, []);

  const getProfile = useCallback((userId: string): UserProfile | undefined => {
    if (userId === currentUser.id) return currentUser;
    return discoverProfiles.find(p => p.id === userId);
  }, []);

  const getConversation = useCallback((matchId: string): Conversation | undefined => {
    return conversations.find(c => c.matchId === matchId);
  }, [conversations]);

  return (
    <AppContext.Provider
      value={{
        currentUser,
        discoverQueue,
        matches,
        conversations,
        passProfile,
        likeProfile,
        sendMessage,
        getProfile,
        getConversation,
        currentDiscoverIndex,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppState() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppState must be used within AppProvider');
  return ctx;
}
