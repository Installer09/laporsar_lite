'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getReports, getContacts, getKnowledgeBase, getStats } from '@/lib/api';
import { useSocket } from './useSocket';
import { useEffect } from 'react';

function playNotificationSound() {
  if (typeof window === 'undefined') return;
  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;
    
    const audioCtx = new AudioContextClass();
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    
    const now = audioCtx.currentTime;
    
    // Tone 1: High crisp alert ping (D5)
    const osc1 = audioCtx.createOscillator();
    const gain1 = audioCtx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, now);
    gain1.gain.setValueAtTime(0.12, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
    osc1.connect(gain1);
    gain1.connect(audioCtx.destination);
    osc1.start(now);
    osc1.stop(now + 0.3);
    
    // Tone 2: Harmonious lower tone (A4)
    const osc2 = audioCtx.createOscillator();
    const gain2 = audioCtx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(440.00, now + 0.12);
    gain2.gain.setValueAtTime(0.12, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
    osc2.connect(gain2);
    gain2.connect(audioCtx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.5);
  } catch (error) {
    console.warn('Audio notification blocked by browser autoplay policy:', error);
  }
}

export function useDashboardData() {
  const queryClient = useQueryClient();
  const { isConnected, lastMessage } = useSocket();

  useEffect(() => {
    if (lastMessage) {
      // The backend uses both 'type' and 'event' fields for broadcasts
      const msgType = lastMessage.type || (lastMessage as any).event;
      
      if (msgType === 'new_report' || msgType === 'report_updated' || msgType === 'report_deleted') {
        queryClient.invalidateQueries({ queryKey: ['reports'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
        
        if (msgType === 'new_report') {
          playNotificationSound();
        }
      } else if (msgType === 'new_contact') {
        queryClient.invalidateQueries({ queryKey: ['contacts'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
      } else if (msgType === 'chat_message') {
        queryClient.invalidateQueries({ queryKey: ['chat_sessions'] });
        const payload = lastMessage.payload || lastMessage;
        if (payload && (payload as any).session_id) {
          queryClient.invalidateQueries({ queryKey: ['chat_session', (payload as any).session_id] });
        }
      }
    }
  }, [lastMessage, queryClient]);

  const useReportsQuery = () => useQuery({
    queryKey: ['reports'],
    queryFn: getReports,
  });

  const useContactsQuery = () => useQuery({
    queryKey: ['contacts'],
    queryFn: getContacts,
  });

  const useKnowledgeBaseQuery = () => useQuery({
    queryKey: ['knowledge'],
    queryFn: getKnowledgeBase,
  });

  const useStatsQuery = () => useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
  });

  return {
    isConnected,
    useReportsQuery,
    useContactsQuery,
    useKnowledgeBaseQuery,
    useStatsQuery,
  };
}
