import {Message} from "@/types/chatTypes";
import {
  Conversation,
  createConversation,
  loadConversations,
  saveConversations,
  generateConversationTitle,
} from "@/dataStore/persistenceMiddleware";

// Save current conversation to the conversations list
export const saveConversation = (messages: Message[]): Conversation => {
  if (messages.length === 0) {
    throw new Error("Cannot save empty conversation");
  }

  const conversations = loadConversations();
  const newConversation = createConversation(messages);
  
  // Check if this is an update to an existing conversation
  // (e.g., if we're continuing an existing conversation)
  const existingIndex = conversations.findIndex(
    (conv) => conv.id === newConversation.id
  );

  if (existingIndex >= 0) {
    // Update existing conversation
    conversations[existingIndex] = {
      ...newConversation,
      id: conversations[existingIndex].id, // Keep original ID
      createdAt: conversations[existingIndex].createdAt, // Keep original creation date
      updatedAt: new Date().toISOString(),
    };
  } else {
    // Add new conversation
    conversations.push(newConversation);
  }

  // Sort by updatedAt (most recent first)
  conversations.sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  );

  saveConversations(conversations);
  return newConversation;
};

// Delete a conversation
export const deleteConversation = (conversationId: string): void => {
  const conversations = loadConversations();
  const filtered = conversations.filter((conv) => conv.id !== conversationId);
  saveConversations(filtered);
};

// Get a conversation by ID
export const getConversation = (conversationId: string): Conversation | null => {
  const conversations = loadConversations();
  return conversations.find((conv) => conv.id === conversationId) || null;
};

// Export conversation as JSON
export const exportConversationAsJSON = (conversation: Conversation): string => {
  return JSON.stringify(conversation, null, 2);
};

// Export conversation as Markdown
export const exportConversationAsMarkdown = (conversation: Conversation): string => {
  let markdown = `# ${conversation.title}\n\n`;
  markdown += `**Created:** ${new Date(conversation.createdAt).toLocaleString()}\n`;
  markdown += `**Updated:** ${new Date(conversation.updatedAt).toLocaleString()}\n\n`;
  markdown += `---\n\n`;

  conversation.messages.forEach((message, index) => {
    if (message.role === "user" && message.prompt) {
      markdown += `## User Message ${index + 1}\n\n`;
      markdown += `${message.prompt}\n\n`;
    } else if (message.role === "assistant" && message.data) {
      markdown += `## Assistant Response ${index + 1}\n\n`;
      message.data.forEach((systemMessage) => {
        markdown += `### ${systemMessage.agent_name}\n\n`;
        if (systemMessage.instructions) {
          markdown += `**Instructions:** ${systemMessage.instructions}\n\n`;
        }
        if (systemMessage.steps && systemMessage.steps.length > 0) {
          markdown += `**Steps:**\n`;
          systemMessage.steps.forEach((step) => {
            markdown += `- ${step}\n`;
          });
          markdown += `\n`;
        }
        if (systemMessage.output) {
          markdown += `**Output:**\n\n${systemMessage.output}\n\n`;
        }
        markdown += `---\n\n`;
      });
    }
  });

  return markdown;
};

// Download file helper
export const downloadFile = (content: string, filename: string, mimeType: string): void => {
  const blob = new Blob([content], {type: mimeType});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

