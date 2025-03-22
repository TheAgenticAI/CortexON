export type ChatPageProps = {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
};

export type ChatListPageProps = {
  isLoading: boolean;
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>;
};

export interface SystemMessage {
  agent_name: string;
  instructions: string;
  steps: string[];
  output: string;
  status_code: number;
  live_url: string;
}

export interface Message {
  role: string;
  prompt?: string;
  data?: SystemMessage[];
  sent_at?: string;
}

export interface AgentOutput {
  agent: string;
  output: string;
}
