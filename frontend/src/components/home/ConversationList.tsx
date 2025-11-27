import {useState, useEffect} from "react";
import {useDispatch} from "react-redux";
import {
  MessageSquare,
  Trash2,
  Download,
  X,
  FileText,
  FileJson,
  Plus,
  History,
} from "lucide-react";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
import {ScrollArea} from "../ui/scroll-area";
import {
  Conversation,
  loadConversations,
} from "@/dataStore/persistenceMiddleware";
import {
  saveConversation,
  deleteConversation,
  exportConversationAsJSON,
  exportConversationAsMarkdown,
  downloadFile,
} from "@/utils/conversationUtils";
import {setMessages, clearMessages} from "@/dataStore/messagesSlice";
import {Message} from "@/types/chatTypes";

interface ConversationListProps {
  isOpen: boolean;
  onClose: () => void;
  currentMessages: Message[];
}

export const ConversationList = ({
  isOpen,
  onClose,
  currentMessages,
}: ConversationListProps) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const dispatch = useDispatch();

  useEffect(() => {
    if (isOpen) {
      loadConversationsList();
    }
  }, [isOpen]);

  const loadConversationsList = () => {
    const loaded = loadConversations();
    setConversations(loaded);
  };

  const handleSaveCurrent = () => {
    if (currentMessages.length === 0) {
      alert("No messages to save");
      return;
    }
    try {
      saveConversation(currentMessages);
      loadConversationsList();
      alert("Conversation saved successfully!");
    } catch (error) {
      alert(`Error saving conversation: ${error}`);
    }
  };

  const handleLoadConversation = (conversation: Conversation) => {
    dispatch(setMessages(conversation.messages));
    onClose();
  };

  const handleDeleteConversation = (
    e: React.MouseEvent,
    conversationId: string
  ) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this conversation?")) {
      deleteConversation(conversationId);
      loadConversationsList();
    }
  };

  const handleExportJSON = (
    e: React.MouseEvent,
    conversation: Conversation
  ) => {
    e.stopPropagation();
    const json = exportConversationAsJSON(conversation);
    const filename = `conversation_${conversation.id}_${new Date().toISOString().split("T")[0]}.json`;
    downloadFile(json, filename, "application/json");
  };

  const handleExportMarkdown = (
    e: React.MouseEvent,
    conversation: Conversation
  ) => {
    e.stopPropagation();
    const markdown = exportConversationAsMarkdown(conversation);
    const filename = `conversation_${conversation.id}_${new Date().toISOString().split("T")[0]}.md`;
    downloadFile(markdown, filename, "text/markdown");
  };

  const handleNewConversation = () => {
    if (currentMessages.length > 0) {
      if (
        confirm(
          "Starting a new conversation will clear current messages. Do you want to save the current conversation first?"
        )
      ) {
        handleSaveCurrent();
      }
    }
    dispatch(clearMessages());
    onClose();
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <div className="relative flex flex-col w-full max-w-md bg-background border-r shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5" />
            <h2 className="text-lg font-semibold">Conversations</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Actions */}
        <div className="flex gap-2 p-4 border-b">
          <Button
            onClick={handleNewConversation}
            variant="outline"
            className="flex-1"
            size="sm"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Chat
          </Button>
          <Button
            onClick={handleSaveCurrent}
            variant="outline"
            className="flex-1"
            size="sm"
            disabled={currentMessages.length === 0}
          >
            <MessageSquare className="h-4 w-4 mr-2" />
            Save Current
          </Button>
        </div>

        {/* Conversations List */}
        <ScrollArea className="flex-1">
          <div className="p-4 space-y-2">
            {conversations.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No saved conversations yet</p>
                <p className="text-sm mt-2">
                  Start a conversation and save it to see it here
                </p>
              </div>
            ) : (
              conversations.map((conversation) => (
                <Card
                  key={conversation.id}
                  className="p-3 cursor-pointer hover:bg-accent transition-colors group"
                  onClick={() => handleLoadConversation(conversation)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-sm truncate">
                        {conversation.title}
                      </h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        {formatDate(conversation.updatedAt)}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {conversation.messages.length} message
                        {conversation.messages.length !== 1 ? "s" : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={(e) => handleExportJSON(e, conversation)}
                        title="Export as JSON"
                      >
                        <FileJson className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={(e) => handleExportMarkdown(e, conversation)}
                        title="Export as Markdown"
                      >
                        <FileText className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive"
                        onClick={(e) => handleDeleteConversation(e, conversation.id)}
                        title="Delete conversation"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
};

