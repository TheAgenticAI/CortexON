import {Middleware} from "@reduxjs/toolkit";
import {Message} from "@/types/chatTypes";

const CONVERSATIONS_STORAGE_KEY = "cortexon_conversations";
const CURRENT_CONVERSATION_KEY = "cortexon_current_conversation";

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

// Load conversations from localStorage
export const loadConversations = (): Conversation[] => {
  try {
    const stored = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error("Error loading conversations from localStorage:", error);
  }
  return [];
};

// Save conversations to localStorage
export const saveConversations = (conversations: Conversation[]): void => {
  try {
    localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversations));
  } catch (error) {
    console.error("Error saving conversations to localStorage:", error);
    // Handle quota exceeded error
    if (error instanceof Error && error.name === "QuotaExceededError") {
      // Remove oldest conversations if storage is full
      const sorted = [...conversations].sort(
        (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
      );
      // Keep only the 50 most recent conversations
      const trimmed = sorted.slice(-50);
      localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(trimmed));
    }
  }
};

// Load current conversation from localStorage
export const loadCurrentConversation = (): Message[] => {
  try {
    const stored = localStorage.getItem(CURRENT_CONVERSATION_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error("Error loading current conversation from localStorage:", error);
  }
  return [];
};

// Save current conversation to localStorage
export const saveCurrentConversation = (messages: Message[]): void => {
  try {
    localStorage.setItem(CURRENT_CONVERSATION_KEY, JSON.stringify(messages));
  } catch (error) {
    console.error("Error saving current conversation to localStorage:", error);
  }
};

// Generate a title from the first user message
export const generateConversationTitle = (messages: Message[]): string => {
  const firstUserMessage = messages.find((msg) => msg.role === "user" && msg.prompt);
  if (firstUserMessage?.prompt) {
    // Take first 50 characters of the prompt
    const title = firstUserMessage.prompt.substring(0, 50);
    return title.length < firstUserMessage.prompt.length ? `${title}...` : title;
  }
  return "New Conversation";
};

// Create a new conversation from messages
export const createConversation = (messages: Message[]): Conversation => {
  const now = new Date().toISOString();
  return {
    id: `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    title: generateConversationTitle(messages),
    messages,
    createdAt: now,
    updatedAt: now,
  };
};

// Persistence middleware for Redux
export const persistenceMiddleware: Middleware = (store) => (next) => (action) => {
  const result = next(action);
  const state = store.getState();
  
  // Save current conversation whenever messages change
  if (action.type === "messagesState/setMessages") {
    const messages = state.messagesState.messages;
    saveCurrentConversation(messages);
  }
  
  return result;
};

