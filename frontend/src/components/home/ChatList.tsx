import {
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Component,
  Globe,
  Send,
  SquareCode,
  SquareSlash,
  X,
  Search,
} from "lucide-react";
import {useEffect, useRef, useState} from "react";
import favicon from "../../assets/Favicon-contexton.svg";
import {ScrollArea} from "../ui/scroll-area";

import Markdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkBreaks from "remark-breaks";
import {Skeleton} from "../ui/skeleton";

import {setMessages} from "@/dataStore/messagesSlice";
import {RootState} from "@/dataStore/store";
import {getTimeAgo} from "@/lib/utils";
import {AgentOutput, ChatListPageProps, SystemMessage} from "@/types/chatTypes";
import {useDispatch, useSelector} from "react-redux";
import useWebSocket, {ReadyState} from "react-use-websocket";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
import {Textarea} from "../ui/textarea";
import {CodeBlock} from "./CodeBlock";
import {ErrorAlert} from "./ErrorAlert";
import LoadingView from "./Loading";
import {TerminalBlock} from "./TerminalBlock";

const {VITE_WEBSOCKET_URL} = import.meta.env;

const ChatList = ({isLoading, setIsLoading}: ChatListPageProps) => {
  const [isHovering, setIsHovering] = useState<boolean>(false);
  const [isIframeLoading, setIsIframeLoading] = useState<boolean>(true);
  const [liveUrl, setLiveUrl] = useState<string>("");
  const [animateIframeEntry, setAnimateIframeEntry] = useState<boolean>(false);
  const [outputsList, setOutputsList] = useState<AgentOutput[]>([]);
  const [currentOutput, setCurrentOutput] = useState<number | null>(null);
  const [animateOutputEntry, setAnimateOutputEntry] = useState<boolean>(false);
  const [rows, setRows] = useState(4);
  const [animateSubmit, setAnimateSubmit] = useState<boolean>(false);

  const [humanInputValue, setHumanInputValue] = useState<string>("");
  
  // Deep Research Agent tracking
  const [deepResearchTasks, setDeepResearchTasks] = useState<Array<{
    id: string;
    title: string;
    completed: boolean;
    current: boolean;
    priority?: number;
    dependencies?: string[];
    findingsSummary?: string;
    knowledgeGaps?: string[];
  }>>([]);
  const [currentTaskProgress, setCurrentTaskProgress] = useState<string>("");
  const [researchSources, setResearchSources] = useState<Array<{
    title: string;
    url: string;
    type: string;
    snippet?: string;
    domain?: string;
  }>>([]);
  const [researchFindings, setResearchFindings] = useState<string[]>([]);
  const [currentAction, setCurrentAction] = useState<string>("");
  const [liveSteps, setLiveSteps] = useState<string[]>([]);
  const [overallProgress, setOverallProgress] = useState({ current: 0, total: 0, percent: 0 });
  const [currentQuery, setCurrentQuery] = useState<string>("");
  const [urlPreviews, setUrlPreviews] = useState<Array<{
    url: string;
    domain: string;
    preview: string;
    timestamp: number;
  }>>([]);
  // LLM streaming thoughts
  const [thinkingThoughts, setThinkingThoughts] = useState<Array<{
    content: string;
    reasoning_type: string;
  }>>([]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const thinkingScrollRef = useRef<HTMLDivElement>(null);

  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messages = useSelector(
    (state: RootState) => state.messagesState.messages
  );
  const dispatch = useDispatch();

  const prevMessagesLengthRef = useRef(0);
  const prevSystemMessageLengthRef = useRef(0);

  const adjustHeight = () => {
    if (!textareaRef.current) return;

    // Reset to minimum height
    textareaRef.current.style.height = "auto";

    // Get the scroll height
    const scrollHeight = textareaRef.current.scrollHeight;

    // Calculate how many rows that would be (approx 24px per row)
    const calculatedRows = Math.ceil(scrollHeight / 24);

    // Limit to between 4 and 12 rows
    const newRows = Math.max(4, Math.min(12, calculatedRows));

    setRows(newRows);
  };

  const {sendMessage, lastJsonMessage, readyState} = useWebSocket(
    VITE_WEBSOCKET_URL,
    {
      onOpen: () => {
        if (messages.length > 0 && messages[0]?.prompt) {
          sendMessage(messages[0].prompt);
        }
      },
      onError: () => {
        setIsLoading(false);
      },
      onClose: () => {
        setIsLoading(false);
      },
      reconnectAttempts: 3,
      retryOnError: true,
      shouldReconnect: () => true,
      reconnectInterval: 3000,
    }
  );

  const scrollToBottom = (smooth = true) => {
    if (scrollAreaRef.current) {
      const scrollableDiv = scrollAreaRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (scrollableDiv) {
        const lastMessageElement = scrollAreaRef.current.querySelector(
          ".space-y-4 > div:last-child"
        );

        if (lastMessageElement) {
          lastMessageElement.scrollIntoView({
            behavior: smooth ? "smooth" : "auto",
            block: "end",
          });
        } else {
          scrollableDiv.scrollTo({
            top: scrollableDiv.scrollHeight,
            behavior: smooth ? "smooth" : "auto",
          });
        }
      }
    }
  };

  useEffect(() => {
    if (!lastJsonMessage) return;

    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.role === "system") {
      setIsLoading(true);

      const lastMessageData = lastMessage.data || [];
      const {agent_name, instructions, steps, output, status_code, live_url, message_id} =
        lastJsonMessage as SystemMessage;

      console.log(lastJsonMessage);

      if (live_url && liveUrl.length === 0) {
        setCurrentOutput(null);
        setTimeout(() => {
          setLiveUrl(live_url);
          setIsIframeLoading(true);
          setAnimateIframeEntry(true);
        }, 300);
      } else if (agent_name !== "Web Surfer") {
        setLiveUrl("");
      }

      // Parse Deep Research Agent data
      if (agent_name === "Deep Research Agent" && steps) {
        console.log("🔍 Deep Research Agent Steps:", steps); // Debug log
        
        steps.forEach((step, index) => {
          console.log(`📝 Processing step ${index}:`, step); // Debug log
          
          // Try to parse as JSON first
          try {
            const data = JSON.parse(step);
            console.log("📊 Parsed JSON data:", data);
            
            switch (data.type) {
              case "plan_created":
                // Set all tasks from the plan
                if (data.tasks) {
                  setDeepResearchTasks(data.tasks.map((task: any) => ({
                    id: task.id,
                    title: task.title,
                    completed: false,
                    current: false,
                    priority: task.priority,
                    dependencies: task.dependencies
                  })));
                  setOverallProgress({ current: 0, total: data.total_tasks, percent: 0 });
                }
                break;
                
              case "task_started":
                // Update current task
                setDeepResearchTasks(prev => prev.map(task => ({
                  ...task,
                  current: task.id === data.task_id
                })));
                setCurrentTaskProgress(data.task_title);
                if (data.progress) {
                  // Adjust progress to show actual completed tasks (current - 1)
                  setOverallProgress({
                    ...data.progress,
                    current: data.progress.current
                  });
                }
                break;
                
              case "task_completed":
                // Mark task as completed and clear current task progress
                setDeepResearchTasks(prev => prev.map(task => 
                  task.id === data.task_id 
                    ? { 
                        ...task, 
                        completed: true, 
                        current: false,
                        findingsSummary: data.findings_summary,
                        knowledgeGaps: data.knowledge_gaps
                      }
                    : task
                ));
                // Clear current task progress when task completes
                setCurrentTaskProgress("");
                setCurrentAction("");
                if (data.progress) {
                  setOverallProgress(data.progress);
                }
                break;
                
              case "search_completed":
                // Add sources with better structure
                if (data.sources) {
                  setCurrentQuery(data.query);
                  setResearchSources(prev => {
                    const newSources = data.sources.filter((source: any) => 
                      !prev.some(existing => existing.url === source.url)
                    ).map((source: any) => ({
                      ...source,
                      type: "search",
                      domain: source.url.replace(/https?:\/\//, '').split('/')[0]
                    }));
                    return [...prev, ...newSources];
                  });
                }
                break;
                
              case "content_extracted":
                // Add URL preview
                if (data.url && data.preview) {
                  setUrlPreviews(prev => {
                    const exists = prev.some(p => p.url === data.url);
                    if (!exists) {
                      return [...prev, {
                        url: data.url,
                        domain: data.domain,
                        preview: data.preview,
                        timestamp: Date.now()
                      }].slice(-10); // Keep last 10 previews
                    }
                    return prev;
                  });
                }
                break;
                
              case "findings_discovered":
                // Add findings from analysis
                if (data.findings) {
                  setResearchFindings(prev => {
                    if (!prev.includes(data.findings)) {
                      return [...prev, data.findings].slice(-10); // Keep last 10 findings
                    }
                    return prev;
                  });
                }
                break;
                
              case "agent_thoughts":
                // Push latest thoughts (keep last 10)
                if (data.content) {
                  setThinkingThoughts(prev => {
                    const newThought = {
                      content: data.content,
                      reasoning_type: data.reasoning_type || "general",
                    };

                    // Merge and deduplicate by content while preserving order (latest occurrence wins)
                    const merged = [...prev, newThought];
                    const deduped = merged.filter(
                      (t, idx, arr) =>
                        arr.findIndex(other => other.content === t.content) === idx
                    );

                    // Keep only the last 10 unique thoughts
                    return deduped.slice(-10);
                  });
                }
                break;
                
              default:
                // For other types, just update current action
                if (data.message) {
                  setCurrentAction(data.message);
                }
            }
            
            // Always add to live steps
            setLiveSteps(prev => [...prev, data.message || step].slice(-10));
            
          } catch (e) {
            // If not JSON, parse as before (fallback)
            console.log("Not JSON, parsing as text:", step);
            
            // Simple text parsing for backward compatibility
            if (/working|processing|executing|starting|current/i.test(step)) {
              setCurrentAction(step);
            }
            
            // Add to live steps
            setLiveSteps(prev => [...prev, step].slice(-10));
          }
        });
      }

      // Check if we already have a message with this message_id
      const existingMessageIndex = lastMessageData.findIndex(
        (msg: SystemMessage) => msg.message_id === message_id
      );

      let updatedLastMessageData;
      if (existingMessageIndex !== -1 && message_id) {
        // If we have a message_id and it already exists, update that specific message
        let filteredSteps = steps;
        if (agent_name === "Web Surfer") {
          const plannerStep = steps.find((step) => step.startsWith("Plan"));
          filteredSteps = plannerStep
            ? [
                plannerStep,
                ...steps.filter((step) => step.startsWith("Current")),
              ]
            : steps.filter((step) => step.startsWith("Current"));
        }
        updatedLastMessageData = [...lastMessageData];
        updatedLastMessageData[existingMessageIndex] = {
          agent_name,
          instructions,
          steps: filteredSteps,
          output,
          status_code,
          live_url,
          message_id
        };
      } else {
        // If message_id doesn't exist or we don't have a message_id, add a new entry
        updatedLastMessageData = [
          ...lastMessageData,
          {
            agent_name,
            instructions,
            steps,
            output,
            status_code,
            live_url,
            message_id: message_id || `${agent_name}-${Date.now()}` // Fallback unique ID if message_id isn't provided
          },
        ];
      }

      if (
        output &&
        output.length > 0 &&
        agent_name !== "Web Surfer" &&
        agent_name !== "Human Input"
      ) {
        if (agent_name === "Orchestrator") {
          setIsLoading(false);
        }

        if (status_code === 200) {
          setOutputsList((prevList) => {
            // If we have a message_id, look for an exact match
            // If not found, create a new entry rather than updating by agent name
            const indexByMessageId = message_id 
              ? prevList.findIndex(item => item.id === message_id)
              : -1;
              
            let newList;
            let newOutputIndex;

            if (indexByMessageId >= 0) {
              // Update the existing entry with matching message_id
              newList = [...prevList];
              newList[indexByMessageId] = {
                agent: agent_name,
                output,
                id: message_id
              };
              newOutputIndex = indexByMessageId;
            } else {
              // Create a new entry with this output
              newList = [...prevList, {
                agent: agent_name,
                output,
                id: message_id || `${agent_name}-${Date.now()}`
              }];
              newOutputIndex = newList.length - 1;
            }

            setAnimateOutputEntry(false);

            setTimeout(() => {
              setCurrentOutput(newOutputIndex);
              setAnimateOutputEntry(true);
            }, 300);

            return newList;
          });
        }
      }

      if (agent_name === "Human Input") {
        if (output && output.length > 0) {
          setIsLoading(true);
        } else {
          setIsLoading(false);
        }
        setTimeout(() => {
          setCurrentOutput(null);
        }, 300);
      }

      const updatedMessages = [
        ...messages.slice(0, messages.length - 1),
        {
          ...lastMessage,
          data: updatedLastMessageData,
        },
      ];

      if (JSON.stringify(updatedMessages) !== JSON.stringify(messages)) {
        dispatch(setMessages(updatedMessages));
      }
    }
  }, [lastJsonMessage, messages, setIsLoading, dispatch, liveUrl]);

  const getOutputBlock = (type: string, output: string | undefined) => {
    if (!output) return null;

    switch (type) {
      case "Coder Agent":
        return <CodeBlock content={output} />;
      case "Code Executor Agent":
        return <TerminalBlock content={output} />;
      case "Executor Agent":
        return <TerminalBlock content={output} />;
      default:
        return (
          <div className="markdown-container text-base leading-7 break-words p-2">
            <Markdown
              remarkPlugins={[remarkBreaks]}
              rehypePlugins={[rehypeRaw]}
              components={{
                code({className, children, ...props}) {
                  return (
                    <pre className="code-block">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                  );
                },
                h1: ({children}) => (
                  <h1 className="text-2xl font-bold mt-6 mb-4">{children}</h1>
                ),
                h2: ({children}) => (
                  <h2 className="text-xl font-bold mt-5 mb-3">{children}</h2>
                ),
                h3: ({children}) => (
                  <h3 className="text-lg font-bold mt-4 mb-2">{children}</h3>
                ),
                h4: ({children}) => (
                  <h4 className="text-base font-bold mt-3 mb-2">{children}</h4>
                ),
                h5: ({children}) => (
                  <h5 className="text-sm font-bold mt-3 mb-1">{children}</h5>
                ),
                h6: ({children}) => (
                  <h6 className="text-xs font-bold mt-3 mb-1">{children}</h6>
                ),
                p: ({children}) => <p className="mb-4">{children}</p>,
                a: ({href, children}) => (
                  <a
                    href={href}
                    className="text-primary hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {children}
                  </a>
                ),
                ul: ({children}) => (
                  <ul className="list-disc pl-6 mb-4">{children}</ul>
                ),
                ol: ({children}) => (
                  <ol className="list-decimal pl-6 mb-4">{children}</ol>
                ),
                li: ({children}) => <li className="mb-2">{children}</li>,
              }}
            >
              {output}
            </Markdown>
          </div>
        );
    }
  };

  const getAgentIcon = (type: string) => {
    switch (type) {
      case "Coder Agent":
        return (
          <SquareCode size={20} absoluteStrokeWidth className="text-primary" />
        );

      case "Coder Executor Agent":
        return (
          <SquareSlash size={20} absoluteStrokeWidth className="text-primary" />
        );

      case "Executor Agent":
        return (
          <SquareSlash size={20} absoluteStrokeWidth className="text-primary" />
        );

      case "Web Surfer":
        return <Globe size={20} absoluteStrokeWidth className="text-primary" />;

      case "Planner Agent":
        return (
          <BrainCircuit
            size={20}
            absoluteStrokeWidth
            className="text-primary"
          />
        );

      case "Deep Research Agent":
        return (
          <Search size={20} absoluteStrokeWidth className="text-primary" />
        );

      default:
        return (
          <Component size={20} absoluteStrokeWidth className="text-primary" />
        );
    }
  };

  const getAgentOutputCard = (type: string) => {
    switch (type) {
      case "Coder Agent":
        return (
          <p className="flex items-center gap-4">
            <SquareCode
              size={20}
              absoluteStrokeWidth
              className="text-primary"
            />{" "}
            Check Generated Code
          </p>
        );

      case "Coder Executor Agent":
        return (
          <p className="flex items-center gap-4">
            <SquareSlash
              size={20}
              absoluteStrokeWidth
              className="text-primary"
            />
            Check Executor Results
          </p>
        );

      case "Deep Research Agent":
        return (
          <p className="flex items-center gap-4">
            <Search
              size={20}
              absoluteStrokeWidth
              className="text-primary"
            />
            View Research Report
          </p>
        );

      case "Executor Agent":
        return (
          <p className="flex items-center gap-4">
            <SquareSlash
              size={20}
              absoluteStrokeWidth
              className="text-primary"
            />
            Check Executor Results
          </p>
        );

      case "Web Surfer":
        return (
          <p className="flex items-center gap-4">
            <Globe size={20} absoluteStrokeWidth className="text-primary" />
            Check Browsing History Replay
          </p>
        );

      case "Planner Agent":
        return (
          <p className="flex items-center gap-4">
            <BrainCircuit
              size={20}
              absoluteStrokeWidth
              className="text-primary"
            />
            Check Generated Plan
          </p>
        );

      default:
        return (
          <p className="flex items-center gap-4">
            <Component size={20} absoluteStrokeWidth className="text-primary" />
            Check Output
          </p>
        );
    }
  };

  const handleOutputSelection = (index: number) => {
    if (currentOutput === index) return;

    if (currentOutput !== null) {
      setAnimateOutputEntry(false);

      setTimeout(() => {
        setCurrentOutput(index);
        setAnimateOutputEntry(true);
      }, 300);
    } else {
      setCurrentOutput(index);
      setAnimateOutputEntry(true);
    }
  };

  useEffect(() => {
    const currentMessagesLength = messages.length;
    let shouldScroll = false;

    if (currentMessagesLength > prevMessagesLengthRef.current) {
      shouldScroll = true;
    } else if (
      currentMessagesLength > 0 &&
      messages[currentMessagesLength - 1].role === "system"
    ) {
      const systemMessage = messages[currentMessagesLength - 1];
      const currentSystemDataLength = systemMessage.data?.length || 0;

      if (currentSystemDataLength > prevSystemMessageLengthRef.current) {
        shouldScroll = true;
      }

      prevSystemMessageLengthRef.current = currentSystemDataLength;
    }

    prevMessagesLengthRef.current = currentMessagesLength;

    if (shouldScroll) {
      setTimeout(scrollToBottom, 100);
    }
  }, [messages]);

  useEffect(() => {
    scrollToBottom(false);

    const handleResize = () => {
      scrollToBottom(false);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  useEffect(() => {
    if (!liveUrl) {
      setAnimateIframeEntry(false);
    }
  }, [liveUrl]);

  useEffect(() => {
    if (currentOutput === null) {
      setAnimateOutputEntry(false);
    }
  }, [currentOutput]);

  window.addEventListener("message", function (event) {
    if (event.data === "browserbase-disconnected") {
      console.log("Message received from iframe:", event.data);
      setLiveUrl("");
    }
  });

  const chatContainerWidth = liveUrl || currentOutput !== null ? "50%" : "65%";

  const outputPanelClasses = `border-2 rounded-xl w-[50%] flex flex-col h-[95%] justify-between items-center transition-all duration-700 ease-in-out ${
    animateOutputEntry
      ? "opacity-100 translate-x-0 animate-fade-in animate-once animate-duration-1000"
      : "opacity-0 translate-x-2"
  }`;

  const handleHumanInputSubmit = () => {
    if (humanInputValue.trim()) {
      sendMessage(humanInputValue);
      setHumanInputValue("");
      setAnimateSubmit(true);
      setIsLoading(true);
    }
  };

  // Check if Deep Research Agent is active
  const isDeepResearchActive = messages.some(message => 
    message.data?.some(systemMessage => systemMessage.agent_name === "Deep Research Agent")
  );

  // Auto-scroll thinking section to newest thought
  useEffect(() => {
    if (thinkingScrollRef.current && thinkingThoughts.length > 0) {
      const scrollElement = thinkingScrollRef.current;
      setTimeout(() => {
        scrollElement.scrollTo({
          top: scrollElement.scrollHeight,
          behavior: 'smooth'
        });
      }, 100);
    }
  }, [thinkingThoughts]);

  return (
    <div className="w-full h-full flex justify-center items-center px-4 gap-4">
      {/* Deep Research Interface */}


      <div
        className="h-full flex flex-col items-center space-y-4 pt-8 transition-all duration-500 ease-in-out relative"
        style={{width: chatContainerWidth}}
      >
        <ScrollArea className="h-[95%] w-full" ref={scrollAreaRef}>
          <div className="space-y-6 pr-5 w-full">
            {messages.map((message, idx) => {
              return message.role === "user" ? (
                <div
                  className="flex flex-col justify-end items-end space-y-1 animate-fade-in animate-once animate-duration-300 animate-ease-in-out"
                  key={idx}
                  onMouseEnter={() => setIsHovering(true)}
                  onMouseLeave={() => setIsHovering(false)}
                >
                  {message.sent_at && message.sent_at.length > 0 && (
                    <p
                      className={`text-sm transition-colors duration-300 ease-in-out ${
                        !isHovering
                          ? "text-background"
                          : "text-muted-foreground"
                      }`}
                    >
                      {getTimeAgo(message.sent_at)}
                    </p>
                  )}
                  <div
                    className="bg-secondary text-secondary-foreground rounded-lg p-3 break-words 
                    max-w-[80%] transform transition-all duration-300 hover:shadow-md hover:-translate-y-1 animate-fade-right animate-once animate-duration-500"
                  >
                    {message.prompt}
                  </div>
                </div>
              ) : (
                <div
                  className="space-y-2 animate-fade-in animate-once animate-duration-500"
                  key={idx}
                >
                  {readyState === ReadyState.CONNECTING ? (
                    <>
                      <Skeleton className="h-[3vh] w-[10%] animate-pulse" />
                      <Skeleton className="h-[2vh] w-[80%] animate-pulse animate-delay-100" />
                      <Skeleton className="h-[2vh] w-[60%] animate-pulse animate-delay-200" />
                      <Skeleton className="h-[2vh] w-[40%] animate-pulse animate-delay-300" />
                    </>
                  ) : (
                    <>
                      <div className="flex item-center gap-4 animate-fade-down animate-once animate-duration-500">
                        <img
                          src={favicon}
                          className="animate-spin-slow animate-duration-3000 hover:animate-bounce"
                        />
                        <p className="text-2xl animate-fade-right animate-once animate-duration-700">
                          CortexOn
                        </p>
                      </div>
                      <div className="ml-12 max-w-[87%]">
                        {message.data?.map((systemMessage, index) =>
                          systemMessage.agent_name === "Orchestrator" ? (
                            <div
                              className="space-y-5 bg-background mb-4 max-w-full animate-fade-in animate-once animate-delay-300"
                              key={systemMessage.message_id || index}
                            >
                              <div className="flex flex-col gap-3 text-gray-300">
                                {systemMessage.steps &&
                                  systemMessage.steps.map((text, i) => (
                                    <div
                                      key={i}
                                      className="flex gap-2 text-gray-300 items-start animate-fade-left animate-once animate-duration-500"
                                      style={{
                                        animationDelay: `${i * 150}ms`,
                                      }}
                                    >
                                      <div className="h-4 w-4 flex-shrink-0 mt-[0.15rem] transition-transform duration-300 hover:scale-125">
                                        <SquareSlash
                                          size={20}
                                          absoluteStrokeWidth
                                          className="text-[#BD24CA]"
                                        />
                                      </div>
                                      <span className="text-base break-words">
                                        {text}
                                      </span>
                                    </div>
                                  ))}
                              </div>
                            </div>
                          ) : systemMessage.agent_name === "Human Input" ? (
                            <div
                              className="space-y-5 bg-background mb-4 w-full animate-fade-in animate-once animate-delay-300"
                              key={systemMessage.message_id || index}
                            >
                              <div className="transform transition-transform duration-300 hover:scale-105 animate-fade-right animate-once animate-duration-500">
                                <div className="markdown-container text-base leading-7 break-words p-2">
                                  <Markdown
                                    remarkPlugins={[remarkBreaks]}
                                    rehypePlugins={[rehypeRaw]}
                                    components={{
                                      code({className, children, ...props}) {
                                        return (
                                          <pre className="code-block">
                                            <code
                                              className={className}
                                              {...props}
                                            >
                                              {children}
                                            </code>
                                          </pre>
                                        );
                                      },
                                      h1: ({children}) => (
                                        <h1 className="text-2xl font-bold mt-6 mb-4">
                                          {children}
                                        </h1>
                                      ),
                                      h2: ({children}) => (
                                        <h2 className="text-xl font-bold mt-5 mb-3">
                                          {children}
                                        </h2>
                                      ),
                                      h3: ({children}) => (
                                        <h3 className="text-lg font-bold mt-4 mb-2">
                                          {children}
                                        </h3>
                                      ),
                                      h4: ({children}) => (
                                        <h4 className="text-base font-bold mt-3 mb-2">
                                          {children}
                                        </h4>
                                      ),
                                      h5: ({children}) => (
                                        <h5 className="text-sm font-bold mt-3 mb-1">
                                          {children}
                                        </h5>
                                      ),
                                      h6: ({children}) => (
                                        <h6 className="text-xs font-bold mt-3 mb-1">
                                          {children}
                                        </h6>
                                      ),
                                      p: ({children}) => (
                                        <p className="mb-4">{children}</p>
                                      ),
                                      a: ({href, children}) => (
                                        <a
                                          href={href}
                                          className="text-primary hover:underline"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                        >
                                          {children}
                                        </a>
                                      ),
                                      ul: ({children}) => (
                                        <ul className="list-disc pl-6 mb-4">
                                          {children}
                                        </ul>
                                      ),
                                      ol: ({children}) => (
                                        <ol className="list-decimal pl-6 mb-4">
                                          {children}
                                        </ol>
                                      ),
                                      li: ({children}) => (
                                        <li className="mb-2">{children}</li>
                                      ),
                                    }}
                                  >
                                    {systemMessage.instructions}
                                  </Markdown>
                                </div>
                              </div>
                              {systemMessage.output &&
                              systemMessage.output.length > 0 ? (
                                <div className="flex flex-col justify-end items-end space-y-1 animate-fade-in animate-once animate-duration-300 animate-ease-in-out">
                                  <div
                                    className="bg-secondary text-secondary-foreground text-right rounded-lg p-3 break-words 
                    max-w-[80%] min-w-[10%] transform transition-all duration-300 hover:shadow-md hover:-translate-y-1 animate-fade-right animate-once animate-duration-500"
                                  >
                                    {systemMessage.output}
                                  </div>
                                </div>
                              ) : (
                                <div className="relative w-[100%] transition-all duration-300 hover:scale-[1.01] focus-within:scale-[1.01]">
                                  <Textarea
                                    ref={textareaRef}
                                    draggable={false}
                                    placeholder="Please enter your input here..."
                                    rows={rows}
                                    value={humanInputValue}
                                    onChange={(e) => {
                                      setHumanInputValue(e.target.value);
                                      adjustHeight();
                                    }}
                                    className={`w-full max-h-[20vh] focus:shadow-lg resize-none pb-5 transition-all duration-300 ${
                                      humanInputValue
                                        ? "border-primary border-2"
                                        : "border"
                                    }`}
                                    style={{
                                      overflowY: rows >= 12 ? "auto" : "hidden",
                                    }}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") {
                                        if (e.shiftKey) {
                                          // Shift+Enter - insert a new line
                                          setHumanInputValue(
                                            (prev) => prev + "\n"
                                          );
                                        } else {
                                          // Just Enter - submit the form
                                          e.preventDefault(); // Prevent default newline behavior
                                          if (humanInputValue.length > 0) {
                                            handleHumanInputSubmit();
                                          }
                                        }
                                      }
                                    }}
                                  />
                                  {humanInputValue.trim().length > 0 && (
                                    <Button
                                      size="icon"
                                      className={`absolute right-2 top-2 transition-all duration-300 ${
                                        animateSubmit
                                          ? "scale-90"
                                          : "hover:scale-110"
                                      }`}
                                      onClick={handleHumanInputSubmit}
                                    >
                                      <Send size={20} absoluteStrokeWidth />
                                    </Button>
                                  )}
                                  {humanInputValue.trim().length > 0 && (
                                    <p className="text-[13px] text-muted-foreground absolute right-3 bottom-3 pointer-events-none animate-fade-in animate-duration-300">
                                      press shift + enter to go to new line
                                    </p>
                                  )}
                                </div>
                              )}
                            </div>
                          ) : systemMessage.agent_name === "Deep Research Agent" ? (
                            <Card
                              key={systemMessage.message_id || index}
                              className="bg-background mb-4 transition-all duration-500 ease-in-out transform hover:shadow-md hover:-translate-y-1 animate-fade-up animate-once animate-duration-700 max-w-full"
                              style={{animationDelay: `${index * 300}ms`}}
                            >
                              <div className="flex h-[600px] w-full overflow-hidden">
                                {/* Main Content */}
                                <div className="flex-1 h-full p-4 space-y-4 overflow-y-auto pr-2">
                                  <div className="bg-secondary border flex items-center gap-2 mb-4 px-3 py-1 rounded-md w-max transform transition-transform duration-300 hover:scale-110 animate-fade-right animate-once animate-duration-500">
                                    {getAgentIcon(systemMessage.agent_name)}
                                    <span className="text-white text-base">
                                      {systemMessage.agent_name}
                                    </span>
                                  </div>
                                  
                                  {/* Research Overview */}
                                  <div className="bg-secondary/10 rounded-lg p-4 space-y-3">
                                    <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                                      <BrainCircuit size={16} className="text-primary" />
                                      Research Intelligence
                                    </h4>
                                    
                                    {/* Key Metrics */}
                                    <div className="bg-background/50 rounded-lg p-3 text-center">
                                      <p className="text-2xl font-bold text-primary">{researchSources.length}</p>
                                      <p className="text-xs text-muted-foreground">Total Sources</p>
                                    </div>
                                  </div>
                                  
                                  {/* Current Focus */}
                                  {deepResearchTasks.length > 0 && (
                                    <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
                                      <h4 className="text-sm font-medium text-foreground mb-2">Current Focus</h4>
                                      <p className="text-sm text-muted-foreground">
                                        {currentTaskProgress || "Awaiting task..."}
                                      </p>
                                      
                                    </div>
                                  )}
                                  
                                  {/* Thinking Section */}
                                  {thinkingThoughts.length > 0 && (
                                    <div className="space-y-3">
                                      <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                                        <div className="w-1 h-4 bg-primary rounded-full animate-pulse"></div>
                                        Thinking
                                      </h4>
                                      <div 
                                        ref={thinkingScrollRef}
                                        className="space-y-2 max-h-64 overflow-y-auto pr-1 scroll-smooth"
                                      >
                                        {thinkingThoughts.slice(-5).map((thought, idx) => (
                                          <div 
                                            key={idx} 
                                            className={`bg-secondary/10 rounded-lg p-2 text-xs text-muted-foreground leading-relaxed transform transition-all duration-500 ease-out ${
                                              idx === thinkingThoughts.slice(-5).length - 1 
                                                ? 'animate-slide-in-bottom opacity-100 translate-y-0 border border-primary/20' 
                                                : 'opacity-80'
                                            }`}
                                            style={{
                                              animationDelay: `${idx * 100}ms`
                                            }}
                                          >
                                            {thought.content}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  
                                  {/* Recent Discoveries */}
                                  {researchFindings.length > 0 && (
                                    <div className="space-y-3">
                                      <h4 className="text-sm font-medium text-foreground">Recent Discoveries</h4>
                                      <div className="space-y-2">
                                        {researchFindings.slice(-2).map((finding, idx) => (
                                          <div key={idx} className="bg-secondary/10 rounded-lg p-3">
                                            <div className="flex items-start gap-2">
                                              <BrainCircuit size={14} className="text-primary mt-0.5 flex-shrink-0" />
                                              <p className="text-xs text-muted-foreground line-clamp-3">
                                                {finding}
                                              </p>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>

                                                                {/* Deep Research Sidebar - Futuristic Design */}
                                <div className="w-96 bg-gradient-to-b from-secondary/5 to-secondary/10 border-l border-border overflow-hidden">
                                  <div className="h-full flex flex-col">
                                    {/* Header with Progress */}
                                    <div className="p-4 border-b border-border bg-background/50 backdrop-blur-sm">
                                      <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-3">
                                          <div className="relative">
                                            <div className="w-10 h-10 bg-primary/20 rounded-xl flex items-center justify-center">
                                              <Search size={18} className="text-primary" />
                                            </div>
                                            <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                                          </div>
                                          <div>
                                            <h3 className="text-base font-semibold text-foreground">Deep Research</h3>
                                            <p className="text-xs text-muted-foreground">Autonomous Intelligence</p>
                                          </div>
                                        </div>
                                        <div className="text-right">
                                          <p className="text-2xl font-bold text-primary">{overallProgress.percent}%</p>
                                          <p className="text-xs text-muted-foreground">{overallProgress.current}/{overallProgress.total} tasks</p>
                                        </div>
                                      </div>
                                      
                                      {/* Overall Progress Bar */}
                                      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                                        <div 
                                          className="h-full bg-gradient-to-r from-primary to-primary/60 transition-all duration-1000 ease-out"
                                          style={{ width: `${overallProgress.percent}%` }}
                                        ></div>
                                      </div>
                                    </div>

                                    {/* Scrollable Content */}
                                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                      {/* Task Timeline - Show only current and previous tasks */}
                                      {deepResearchTasks.length > 0 && (
                                        <div className="space-y-3">
                                          <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                                            <div className="w-1 h-4 bg-primary rounded-full"></div>
                                            Research Progress
                                          </h4>
                                          <div className="relative">
                                            {(() => {
                                              // Progressive display: show completed tasks + current task + next task (if current exists)
                                              const completedTasks = deepResearchTasks.filter(task => task.completed);
                                              const currentTask = deepResearchTasks.find(task => task.current);
                                              const currentIndex = currentTask ? deepResearchTasks.findIndex(task => task.current) : -1;
                                              
                                              const tasksToShow = [];
                                              
                                              // Add all completed tasks
                                              completedTasks.forEach(task => {
                                                tasksToShow.push(task);
                                              });
                                              
                                              // Add current task if it exists and isn't already in completed
                                              if (currentTask && !currentTask.completed) {
                                                tasksToShow.push(currentTask);
                                              }
                                              
                                              // Add next task if current task exists and there's a next one
                                              if (currentIndex >= 0 && currentIndex < deepResearchTasks.length - 1) {
                                                const nextTask = deepResearchTasks[currentIndex + 1];
                                                if (!nextTask.completed && !nextTask.current) {
                                                  tasksToShow.push(nextTask);
                                                }
                                              }
                                              
                                              return tasksToShow.map((task, index) => (
                                                <div 
                                                  key={task.id} 
                                                  className={`relative transform transition-all duration-700 ease-out ${
                                                    task.current ? 'animate-slide-in-right' : ''
                                                  }`}
                                                  style={{
                                                    animationDelay: `${index * 200}ms`
                                                  }}
                                                >
                                                  <div className="relative mb-6">
                                                    {/* Connection Line */}
                                                    {index > 0 && (
                                                      <div className={`absolute left-2 -top-6 w-0.5 h-6 transition-colors duration-500 ${
                                                        tasksToShow[index - 1].completed ? 'bg-primary' : 'bg-border'
                                                      }`}></div>
                                                    )}
                                                    
                                                    {/* Task Timeline Item */}
                                                    <div className="flex items-start gap-3">
                                                      {/* Task Node */}
                                                      <div className="flex-shrink-0 mt-1">
                                                        <div className={`w-4 h-4 rounded-full border-2 transition-all duration-500 ${
                                                          task.completed 
                                                            ? 'bg-primary border-primary shadow-md' 
                                                            : task.current 
                                                            ? 'bg-background border-primary animate-pulse shadow-md' 
                                                            : 'bg-background border-border'
                                                        }`}>
                                                          {task.completed && (
                                                            <svg className="w-full h-full p-0.5 text-primary-foreground" fill="currentColor" viewBox="0 0 20 20">
                                                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                                            </svg>
                                                          )}
                                                          {task.current && (
                                                            <div className="w-2 h-2 bg-primary rounded-full absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 animate-ping"></div>
                                                          )}
                                                        </div>
                                                      </div>
                                                      
                                                      {/* Task Content */}
                                                      <div className={`flex-1 min-w-0 transition-all duration-300 ${
                                                        task.current ? 'bg-primary/5 px-3 py-2 rounded-lg border border-primary/10' : ''
                                                      }`}>
                                                        <p className={`text-sm font-medium leading-relaxed ${
                                                          task.current ? 'text-primary' : 
                                                          task.completed ? 'text-foreground' : 'text-muted-foreground'
                                                        }`}>
                                                          {task.title}
                                                        </p>
                                                      </div>
                                                    </div>
                                                  </div>
                                                </div>
                                              ));
                                            })()}
                                          </div>
                                        </div>
                                      )}

                                      {/* Source List */}
                                      {researchSources.length > 0 && (
                                        <div className="space-y-3">
                                          <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                                            <div className="w-1 h-4 bg-primary rounded-full"></div>
                                            Discovered Sources ({researchSources.length})
                                          </h4>
                                          <div className="space-y-2 max-h-64 overflow-y-auto">
                                            {researchSources.map((source, idx) => (
                                              <div 
                                                key={idx}
                                                className="group relative bg-secondary/10 rounded-lg p-3 hover:bg-secondary/20 transition-all cursor-pointer"
                                              >
                                                <div className="flex items-start gap-2">
                                                  <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 bg-primary/10">
                                                    <Globe size={12} className="text-primary/70" />
                                                  </div>
                                                  <div className="flex-1 min-w-0">
                                                    <p className="text-xs font-medium text-foreground line-clamp-1">
                                                      {source.title}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground truncate">
                                                      {source.domain || source.url.replace(/https?:\/\//, '').split('/')[0]}
                                                    </p>
                                                    {source.snippet && (
                                                      <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                                                        {source.snippet}
                                                      </p>
                                                    )}
                                                  </div>
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      )}

                                      {/* Current Query */}
                                      {currentQuery && (
                                        <div className="space-y-3">
                                          <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
                                            <div className="w-1 h-4 bg-primary rounded-full"></div>
                                            Active Search
                                          </h4>
                                          <div className="bg-primary/5 border border-primary/20 rounded-lg p-3">
                                            <p className="text-xs text-foreground italic">"{currentQuery}"</p>
                                          </div>
                                        </div>
                                      )}

                                      {/* Live Activity Stream removed */}
                                    </div>

                                    {/* Footer Status */}
                                    <div className="p-4 border-t border-border bg-background/50 backdrop-blur-sm">
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                                          <span className="text-xs text-muted-foreground">System Active</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                          <span className="text-xs text-muted-foreground">{researchSources.length} total sources</span>
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </Card>
                          ) : (
                            <Card
                              key={systemMessage.message_id || index}
                              className="p-4 bg-background mb-4 w-[98%] transition-all duration-500 ease-in-out transform hover:shadow-md hover:-translate-y-1 animate-fade-up animate-once animate-duration-700"
                              style={{animationDelay: `${index * 300}ms`}}
                            >
                              <div className="bg-secondary border flex items-center gap-2 mb-4 px-3 py-1 rounded-md w-max transform transition-transform duration-300 hover:scale-110 animate-fade-right animate-once animate-duration-500">
                                {getAgentIcon(systemMessage.agent_name)}
                                <span className="text-white text-base">
                                  {systemMessage.agent_name}
                                </span>
                              </div>
                              <div className="space-y-5 px-2">
                                <div className="flex flex-col gap-2 text-gray-300 animate-fade-in animate-once animate-duration-700">
                                  <span className="text-base break-words">
                                    {systemMessage.instructions}
                                  </span>
                                </div>
                                {systemMessage.steps &&
                                  systemMessage.steps.length > 0 && (
                                    <div className="flex flex-col gap-2 text-gray-300">
                                      <p className="text-muted-foreground text-base animate-fade-in animate-once animate-duration-500">
                                        Steps:
                                      </p>
                                      {systemMessage.steps.map((text, i) => (
                                        <div
                                          key={i}
                                          className="flex gap-2 text-gray-300 items-start animate-fade-in animate-once animate-duration-700"
                                          style={{
                                            animationDelay: `${i * 150}ms`,
                                          }}
                                        >
                                          <div className="h-4 w-4 flex-shrink-0 mt-[0.15rem] transition-transform duration-300 hover:scale-125">
                                            <SquareSlash
                                              size={20}
                                              absoluteStrokeWidth
                                              className="text-[#BD24CA]"
                                            />
                                          </div>
                                          <span className="text-base break-words">
                                            <Markdown
                                              rehypePlugins={[rehypeRaw]}
                                            >
                                              {text}
                                            </Markdown>
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                {systemMessage.output &&
                                  systemMessage.output.length > 0 &&
                                  (systemMessage.agent_name !== "Web Surfer" &&
                                  systemMessage.agent_name !== "Human Input" ? (
                                    <div
                                      onClick={() => {
                                        // First try to find by message_id, then fall back to agent name
                                        const outputIndex = systemMessage.message_id 
                                          ? outputsList.findIndex(item => item.id === systemMessage.message_id)
                                          : outputsList.findIndex(item => item.agent === systemMessage.agent_name);
                                        
                                        if (outputIndex >= 0) {
                                          handleOutputSelection(outputIndex);
                                        }
                                      }}
                                      className="rounded-md w- py-2 px-4 bg-secondary text-secondary-foreground flex items-center justify-between cursor-pointer transition-all hover:shadow-md hover:scale-102 duration-300 animate-pulse-once"
                                    >
                                      {getAgentOutputCard(
                                        systemMessage.agent_name
                                      )}
                                      <ChevronRight absoluteStrokeWidth />
                                    </div>
                                  ) : (
                                    <div className="flex flex-col gap-2 text-gray-300">
                                      <p className="text-muted-foreground text-base">
                                        Output:
                                      </p>
                                      {getOutputBlock(
                                        systemMessage.agent_name,
                                        systemMessage.output
                                      )}
                                    </div>
                                  ))}
                              </div>
                            </Card>
                          )
                        )}
                        {message.data &&
                          message.data.find(
                            (systemMessage) =>
                              systemMessage.agent_name === "Orchestrator" &&
                              systemMessage?.output
                          ) && (
                            <div className="space-y-3 animate-fade-in animate-once animate-delay-700 animate-duration-1000 w-[98%]">
                              {(() => {
                                const orchestratorMessage = message.data.find(
                                  (systemMessage) =>
                                    systemMessage.agent_name === "Orchestrator"
                                );
                                return orchestratorMessage?.status_code === 200 ? (
                                  <div
                                    onClick={() => {
                                      // First try to find by message_id, then fall back to agent name
                                      const outputIndex = orchestratorMessage?.message_id 
                                        ? outputsList.findIndex(item => item.id === orchestratorMessage.message_id)
                                        : outputsList.findIndex(item => item.agent === "Orchestrator");
                                      
                                      if (outputIndex >= 0) {
                                        handleOutputSelection(outputIndex);
                                      }
                                    }}
                                    className="rounded-md py-2 bg-[#F7E8FA] text-[#BD24CA] cursor-pointer transition-all hover:shadow-md hover:scale-102 duration-300 animate-pulse-once"
                                  >
                                    <div className="px-3 flex items-center justify-between">
                                      <img
                                        src={favicon}
                                        className="animate-spin-slow animate-duration-3000"
                                      />
                                      <p className="text-xl font-medium">
                                        Task has been completed. Click here to
                                        view results.
                                      </p>
                                      <ChevronRight absoluteStrokeWidth />
                                    </div>
                                  </div>
                                ) : (
                                  <ErrorAlert
                                    errorMessage={orchestratorMessage?.output}
                                  />
                                );
                              })()}
                            </div>
                          )}
                      </div>
                      {isLoading && <LoadingView />}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {/* Human Input Card */}
        {/* {humanInputRequest && (
          <div className="fixed bottom-24 left-0 right-0 flex justify-center items-center z-50">
            <div className="w-[700px] ml-16">
              <Card className="bg-background/95 backdrop-blur-sm border shadow-lg">
                <div className="p-4 space-y-3">
                  <div className="flex items-center gap-2 text-secondary-foreground">
                    <Component size={20} className="text-primary" />
                    <span className="font-medium">Human Input</span>
                  </div>
                  <div className="text-secondary-foreground text-base">
                    {humanInputRequest.question}
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={humanInputValue}
                      onChange={(e) => setHumanInputValue(e.target.value)}
                      className="flex-1 px-3 py-2 bg-secondary/80 text-foreground rounded-md border border-primary/20 focus:border-primary focus:ring-1 focus:ring-primary outline-none text-base"
                      placeholder="Type your response..."
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          handleHumanInputSubmit();
                        }
                      }}
                    />
                    <Button
                      onClick={handleHumanInputSubmit}
                      className="bg-primary hover:bg-primary/90 text-primary-foreground px-6"
                      size="default"
                    >
                      Send
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )} */}
      </div>
      {liveUrl && (
        <div
          className={`border-2 rounded-xl w-[50%] flex flex-col h-[95%] justify-between items-center transition-all duration-700 ease-in-out ${
            animateIframeEntry
              ? "opacity-100 translate-x-0 animate-fade-in animate-once animate-duration-1000"
              : "opacity-0 translate-x-8"
          }`}
        >
          <div className="bg-secondary rounded-t-xl h-[8vh] w-full flex items-center justify-between px-8 animate-fade-down animate-once animate-duration-700">
            <p className="text-2xl text-secondary-foreground animate-fade-right animate-once animate-duration-700">
              Web Agent
            </p>
          </div>
          <div className="w-[98%]">
            {isIframeLoading && (
              <Skeleton className="h-[55vh] w-full rounded-none animate-pulse animate-infinite animate-duration-1500" />
            )}
            <iframe
              key={liveUrl}
              src={liveUrl}
              className={`w-full aspect-video bg-transparent transition-all duration-700 ${
                isIframeLoading
                  ? "opacity-0 scale-95"
                  : "opacity-100 scale-100 animate-fade-in animate-once animate-duration-1000"
              }`}
              title="Browser Preview"
              sandbox="allow-scripts allow-same-origin allow-modals allow-forms allow-popups"
              onLoad={() => {
                setTimeout(() => setIsIframeLoading(false), 300);
              }}
              onError={(e) => {
                console.error("Iframe load error:", e);
                setIsIframeLoading(false);
              }}
              style={{
                display: isIframeLoading ? "none" : "block",
                pointerEvents: "none",
                transformOrigin: "top left",
              }}
            />
          </div>
          <div className="bg-secondary h-[7vh] flex w-full rounded-b-xl justify-end px-4 animate-fade-up animate-once animate-duration-700"></div>
        </div>
      )}
      {outputsList.length > 0 && currentOutput !== null && (
        <div className={outputPanelClasses}>
          <div className="bg-secondary rounded-t-xl h-[8vh] w-full flex items-center justify-between px-8 animate-fade-down animate-once animate-duration-700">
            <p className="text-2xl text-secondary-foreground animate-fade-right animate-once animate-duration-700">
              {outputsList[currentOutput]?.agent === "Orchestrator"
                ? "Final Summary"
                : outputsList[currentOutput]?.agent}
            </p>
            <div className="flex items-center gap-3">
              <X
                className="cursor-pointer hover:text-red-500 transition-colors duration-300"
                onClick={() => {
                  setAnimateOutputEntry(false);
                  setTimeout(() => setCurrentOutput(null), 300);
                }}
              />
            </div>
          </div>
          <div className="h-[71vh] w-full overflow-y-auto scrollbar-thin pr-2">
            {outputsList[currentOutput]?.output && (
              <div
                className={`p-3 w-full h-full transition-all duration-500 ${
                  animateOutputEntry
                    ? "opacity-100 translate-y-0 animate-fade-in animate-once animate-duration-1000"
                    : "opacity-0 translate-y-4"
                }`}
              >
                {getOutputBlock(
                  outputsList[currentOutput]?.agent,
                  outputsList[currentOutput]?.output
                )}
              </div>
            )}
          </div>
          <div className="bg-secondary h-[7vh] flex w-full rounded-b-xl px-4 animate-fade-up animate-once animate-duration-700">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (currentOutput > 0) {
                    handleOutputSelection(currentOutput - 1);
                  }
                }}
                disabled={currentOutput === 0}
                className="transition-all duration-300 hover:bg-primary/10"
              >
                <ChevronLeft /> Previous
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (currentOutput < outputsList.length - 1) {
                    handleOutputSelection(currentOutput + 1);
                  }
                }}
                disabled={currentOutput === outputsList.length - 1}
                className="transition-all duration-300 hover:bg-primary/10"
              >
                Next <ChevronRight />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatList;
