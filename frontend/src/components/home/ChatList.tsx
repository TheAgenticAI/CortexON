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
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import favicon from "../../assets/Favicon-contexton.svg";
import { ScrollArea } from "../ui/scroll-area";

import Markdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkBreaks from "remark-breaks";
import { Skeleton } from "../ui/skeleton";

import { setMessages } from "@/dataStore/messagesSlice";
import { RootState } from "@/dataStore/store";
import { getTimeAgo } from "@/lib/utils";
import { AgentOutput, ChatListPageProps, SystemMessage } from "@/types/chatTypes";
import { useDispatch, useSelector } from "react-redux";
import useWebSocket, { ReadyState } from "react-use-websocket";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Textarea } from "../ui/textarea";
import { CodeBlock } from "./CodeBlock";
import { ErrorAlert } from "./ErrorAlert";
import LoadingView from "./Loading";
import { TerminalBlock } from "./TerminalBlock";

type PlanApprovalState = {
  id: string;
  instructions: string;
};

type StepApprovalState = {
  id: string;
  instructions: string;
  detail: string;
  channel?: string;
  note: string;
};

const { VITE_WEBSOCKET_URL } = import.meta.env;

const ChatList = ({ isLoading, setIsLoading }: ChatListPageProps) => {
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
  const [planApprovalRequest, setPlanApprovalRequest] =
    useState<PlanApprovalState | null>(null);
  const [planDraft, setPlanDraft] = useState<string>("");
  const [planFeedback, setPlanFeedback] = useState<string>("");
  const [showPlanFeedback, setShowPlanFeedback] = useState<boolean>(false);
  const [requireBrowserApproval, setRequireBrowserApproval] =
    useState<boolean>(false);
  const [requireCoderApproval, setRequireCoderApproval] =
    useState<boolean>(false);
  const [stepApprovals, setStepApprovals] = useState<
    Record<string, StepApprovalState>
  >({});

  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  const { sendMessage, lastJsonMessage, readyState } = useWebSocket(
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
      const {
        agent_name,
        instructions,
        steps,
        output,
        status_code,
        live_url,
        metadata,
      } = lastJsonMessage as SystemMessage;

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

      if (agent_name === "Plan Approval") {
        if (status_code === 102) {
          const approvalId =
            (metadata?.approval_id as string) ?? `plan-${Date.now()}`;
          setPlanApprovalRequest((current) => {
            if (current && current.id === approvalId) {
              return current;
            }
            setPlanDraft(output || "");
            setRequireBrowserApproval(
              Boolean(metadata?.require_browser_approval)
            );
            setRequireCoderApproval(Boolean(metadata?.require_coder_approval));
            // Reset feedback state when new plan arrives
            setPlanFeedback("");
            setShowPlanFeedback(false);
            return { id: approvalId, instructions };
          });
        } else if (metadata?.approval_id) {
          setPlanApprovalRequest((current) => {
            if (!current || current.id !== metadata.approval_id) {
              return current;
            }
            return null;
          });
        }
      }

      if (agent_name === "Step Approval") {
        const approvalId =
          (metadata?.approval_id as string) ?? `step-${Date.now()}`;
        if (status_code === 102) {
          setStepApprovals((prev) => {
            if (prev[approvalId]) {
              return prev;
            }
            return {
              ...prev,
              [approvalId]: {
                id: approvalId,
                instructions,
                detail: output,
                channel: (metadata?.channel as string) || undefined,
                note: "",
              },
            };
          });
        } else if (metadata?.approval_id) {
          setStepApprovals((prev) => {
            if (!prev[approvalId]) {
              return prev;
            }
            const updated = { ...prev };
            delete updated[approvalId];
            return updated;
          });
        }
      }

      const agentIndex = lastMessageData.findIndex(
        (agent: SystemMessage) => agent.agent_name === agent_name
      );

      let updatedLastMessageData;
      if (agentIndex !== -1) {
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
        updatedLastMessageData[agentIndex] = {
          agent_name,
          instructions,
          steps: filteredSteps,
          output,
          status_code,
          live_url,
          metadata,
        };
      } else {
        updatedLastMessageData = [
          ...lastMessageData,
          {
            agent_name,
            instructions,
            steps,
            output,
            status_code,
            live_url,
            metadata,
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

        if (status_code === 200 || (agent_name === "Plan Approval" && status_code === 102)) {
          setOutputsList((prevList) => {
            const existingIndex = prevList.findIndex(
              (item) => item.agent === agent_name
            );

            let newList;
            let newOutputIndex;

            if (existingIndex >= 0) {
              newList = [...prevList];
              newList[existingIndex] = { agent: agent_name, output };
              newOutputIndex = existingIndex;
            } else {
              newList = [...prevList, { agent: agent_name, output }];
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
      case "Plan Approval":
        if (planApprovalRequest && planApprovalRequest.id === (planApprovalRequest.id || "")) {
          return (
            <div className="flex flex-col h-full">
              <div 
                className="markdown-container text-base leading-7 break-words p-2 mb-4 flex-grow overflow-y-auto border rounded-md bg-secondary/50"
                contentEditable={false}
                suppressContentEditableWarning={true}
                style={{ userSelect: 'text' }}
              >
                <Markdown
                  remarkPlugins={[remarkBreaks]}
                  rehypePlugins={[rehypeRaw]}
                >
                  {planDraft}
                </Markdown>
              </div>
              <div className="flex flex-col gap-3 text-sm text-muted-foreground mb-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="size-4 accent-primary"
                    checked={requireBrowserApproval}
                    onChange={(e) =>
                      setRequireBrowserApproval(e.target.checked)
                    }
                  />
                  Require approval before each web action
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="size-4 accent-primary"
                    checked={requireCoderApproval}
                    onChange={(e) =>
                      setRequireCoderApproval(e.target.checked)
                    }
                  />
                  Require approval before each coding step
                </label>
              </div>
              <div className="flex gap-3 justify-end">
                <Button
                  variant="secondary"
                  onClick={() => handlePlanApprovalSubmit(false)}
                >
                  Cancel Run
                </Button>
                <Button onClick={() => handlePlanApprovalSubmit(true)}>
                  Approve &amp; Run
                </Button>
              </div>
            </div>
          );
        }
        return (
          <div 
            className="markdown-container text-base leading-7 break-words p-2"
            contentEditable={false}
            suppressContentEditableWarning={true}
            style={{ userSelect: 'text' }}
          >
            <Markdown
              remarkPlugins={[remarkBreaks]}
              rehypePlugins={[rehypeRaw]}
            >
              {output}
            </Markdown>
          </div>
        );
      default:
        return (
          <div className="markdown-container text-base leading-7 break-words p-2">
            <Markdown
              remarkPlugins={[remarkBreaks]}
              rehypePlugins={[rehypeRaw]}
              components={{
                code({ className, children, ...props }) {
                  return (
                    <pre className="code-block">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                  );
                },
                h1: ({ children }) => (
                  <h1 className="text-2xl font-bold mt-6 mb-4">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-xl font-bold mt-5 mb-3">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-lg font-bold mt-4 mb-2">{children}</h3>
                ),
                h4: ({ children }) => (
                  <h4 className="text-base font-bold mt-3 mb-2">{children}</h4>
                ),
                h5: ({ children }) => (
                  <h5 className="text-sm font-bold mt-3 mb-1">{children}</h5>
                ),
                h6: ({ children }) => (
                  <h6 className="text-xs font-bold mt-3 mb-1">{children}</h6>
                ),
                p: ({ children }) => <p className="mb-4">{children}</p>,
                a: ({ href, children }) => (
                  <a
                    href={href}
                    className="text-primary hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {children}
                  </a>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-6 mb-4">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-6 mb-4">{children}</ol>
                ),
                li: ({ children }) => <li className="mb-2">{children}</li>,
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

  const outputPanelClasses = `border-2 rounded-xl w-[50%] flex flex-col h-[95%] justify-between items-center transition-all duration-700 ease-in-out ${animateOutputEntry
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

  const handlePlanApprovalSubmit = (approved: boolean) => {
    if (!planApprovalRequest) return;
    const payload: Record<string, unknown> = {
      type: "plan_approval",
      approval_id: planApprovalRequest.id,
      approved,
      // Note: plan field removed - users cannot manually edit plans
      // They can only approve, request modifications via feedback, or cancel
      require_browser_approval: requireBrowserApproval,
      require_coder_approval: requireCoderApproval,
    };
    sendMessage(JSON.stringify(payload));
    setPlanApprovalRequest(null);
    setPlanDraft("");
    setPlanFeedback("");
    setShowPlanFeedback(false);
    setRequireBrowserApproval(false);
    setRequireCoderApproval(false);
    // Reset loading state when cancelling
    if (!approved) {
      setIsLoading(false);
    }
  };

  const handlePlanFeedbackSubmit = () => {
    if (!planApprovalRequest || !planFeedback.trim()) return;
    const payload: Record<string, unknown> = {
      type: "plan_feedback",
      approval_id: planApprovalRequest.id,
      feedback: planFeedback.trim(),
    };
    sendMessage(JSON.stringify(payload));
    setPlanFeedback("");
    setShowPlanFeedback(false);
    // Clear the plan approval request and draft while new plan generates
    // The new plan will set these again when it arrives
    setPlanApprovalRequest(null);
    setPlanDraft("");
    setIsLoading(true);
  };

  const handleStepNoteChange = (id: string, value: string) => {
    setStepApprovals((prev) => {
      if (!prev[id]) return prev;
      return {
        ...prev,
        [id]: { ...prev[id], note: value },
      };
    });
  };

  const handleStepApprovalDecision = (id: string, approved: boolean) => {
    const state = stepApprovals[id];
    if (!state) return;
    const payload: Record<string, unknown> = {
      type: "step_approval",
      approval_id: id,
      approved,
    };
    if (!approved && state.note.trim().length > 0) {
      payload.reason = state.note.trim();
    }
    sendMessage(JSON.stringify(payload));
    setStepApprovals((prev) => {
      const updated = { ...prev };
      delete updated[id];
      return updated;
    });
  };

  return (
    <div className="w-full h-full flex justify-center items-center px-4 gap-4">
      <div
        className="h-full flex flex-col items-center space-y-4 pt-8 transition-all duration-500 ease-in-out relative"
        style={{ width: chatContainerWidth }}
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
                      className={`text-sm transition-colors duration-300 ease-in-out ${!isHovering
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
                        {message.data?.map((systemMessage, index) => {
                          if (systemMessage.agent_name === "Orchestrator") {
                            return (
                              <div
                                className="space-y-5 bg-background mb-4 max-w-full animate-fade-in animate-once animate-delay-300"
                                key={index}
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
                            );
                          }

                          if (systemMessage.agent_name === "Plan Approval") {
                            const approvalId =
                              (systemMessage.metadata?.approval_id as
                                | string
                                | undefined) ??
                              planApprovalRequest?.id ??
                              "";
                            const showForm =
                              !!planApprovalRequest &&
                              approvalId.length > 0 &&
                              planApprovalRequest.id === approvalId;
                            return (
                              <div
                                className="space-y-5 bg-background mb-4 w-full animate-fade-in animate-once animate-delay-300"
                                key={index}
                              >
                                <div className="markdown-container text-base leading-7 break-words p-2">
                                  <Markdown
                                    remarkPlugins={[remarkBreaks]}
                                    rehypePlugins={[rehypeRaw]}
                                  >
                                    {systemMessage.instructions}
                                  </Markdown>
                                </div>
                                {showForm ? (
                                  <>
                                    <div
                                      onClick={() =>
                                        handleOutputSelection(
                                          outputsList.findIndex(
                                            (item) => item.agent === "Plan Approval"
                                          )
                                        )
                                      }
                                      className="rounded-md py-2 px-4 bg-secondary text-secondary-foreground flex items-center justify-between cursor-pointer transition-all hover:shadow-md hover:scale-102 duration-300 mb-3"
                                    >
                                      <span className="text-base">📋 Click to view plan</span>
                                      <ChevronRight absoluteStrokeWidth />
                                    </div>
                                    {showPlanFeedback ? (
                                      <>
                                        <div className="flex flex-col gap-2">
                                          <label className="text-sm text-muted-foreground">
                                            What changes would you like to see in the plan?
                                          </label>
                                          <Textarea
                                            value={planFeedback}
                                            onChange={(e) => setPlanFeedback(e.target.value)}
                                            placeholder="E.g., Include a visit to the Louvre, add budget considerations, etc."
                                            rows={4}
                                            className="w-full transition-all duration-300"
                                          />
                                        </div>
                                        <div className="flex gap-3 justify-end">
                                          <Button
                                            variant="secondary"
                                            onClick={() => {
                                              setShowPlanFeedback(false);
                                              setPlanFeedback("");
                                            }}
                                          >
                                            Cancel
                                          </Button>
                                          <Button
                                            onClick={handlePlanFeedbackSubmit}
                                            disabled={!planFeedback.trim()}
                                          >
                                            Submit Feedback
                                          </Button>
                                        </div>
                                      </>
                                    ) : (
                                      <>
                                        <div className="flex flex-col gap-3 text-sm text-muted-foreground">
                                          <label className="flex items-center gap-2">
                                            <input
                                              type="checkbox"
                                              className="size-4 accent-primary"
                                              checked={requireBrowserApproval}
                                              onChange={(e) =>
                                                setRequireBrowserApproval(e.target.checked)
                                              }
                                            />
                                            Require approval before each web action
                                          </label>
                                          <label className="flex items-center gap-2">
                                            <input
                                              type="checkbox"
                                              className="size-4 accent-primary"
                                              checked={requireCoderApproval}
                                              onChange={(e) =>
                                                setRequireCoderApproval(e.target.checked)
                                              }
                                            />
                                            Require approval before each coding step
                                          </label>
                                        </div>
                                        <div className="flex gap-3 justify-end">
                                          <Button
                                            variant="secondary"
                                            onClick={() => handlePlanApprovalSubmit(false)}
                                          >
                                            Cancel Run
                                          </Button>
                                          <Button
                                            variant="outline"
                                            onClick={() => setShowPlanFeedback(true)}
                                          >
                                            Request Changes
                                          </Button>
                                          <Button onClick={() => handlePlanApprovalSubmit(true)}>
                                            Approve &amp; Run
                                          </Button>
                                        </div>
                                      </>
                                    )}
                                  </>
                                ) : (
                                  systemMessage.output && systemMessage.output.length > 0 && (
                                    <div
                                      onClick={() =>
                                        handleOutputSelection(
                                          outputsList.findIndex(
                                            (item) => item.agent === "Plan Approval"
                                          )
                                        )
                                      }
                                      className="rounded-md py-2 px-4 bg-secondary text-secondary-foreground flex items-center justify-between cursor-pointer transition-all hover:shadow-md hover:scale-102 duration-300"
                                    >
                                      <span className="text-base">📋 Click to view {systemMessage.metadata?.['approval_id'] ? 'approved' : ''} plan</span>
                                      <ChevronRight absoluteStrokeWidth />
                                    </div>
                                  )
                                )}
                              </div>
                            );
                          }

                          if (systemMessage.agent_name === "Step Approval") {
                            const approvalId = systemMessage.metadata
                              ?.approval_id as string | undefined;
                            const stepState = approvalId
                              ? stepApprovals[approvalId]
                              : undefined;
                            return (
                              <div
                                className="space-y-5 bg-background mb-4 w-full animate-fade-in animate-once animate-delay-300"
                                key={index}
                              >
                                <div className="markdown-container text-base leading-7 break-words p-2">
                                  <Markdown
                                    remarkPlugins={[remarkBreaks]}
                                    rehypePlugins={[rehypeRaw]}
                                  >
                                    {systemMessage.instructions}
                                  </Markdown>
                                </div>
                                <div className="bg-secondary text-secondary-foreground rounded-lg p-3 break-words">
                                  {systemMessage.output}
                                </div>
                                {stepState && (
                                  <>
                                    <Textarea
                                      placeholder="Optional note when rejecting..."
                                      value={stepState.note}
                                      onChange={(e) =>
                                        handleStepNoteChange(stepState.id, e.target.value)
                                      }
                                      className="w-full transition-all duration-300"
                                      rows={4}
                                    />
                                    <div className="flex gap-3 justify-end">
                                      <Button
                                        variant="secondary"
                                        onClick={() =>
                                          handleStepApprovalDecision(stepState.id, false)
                                        }
                                      >
                                        Reject Step
                                      </Button>
                                      <Button
                                        onClick={() =>
                                          handleStepApprovalDecision(stepState.id, true)
                                        }
                                      >
                                        Approve Step
                                      </Button>
                                    </div>
                                  </>
                                )}
                              </div>
                            );
                          }

                          if (systemMessage.agent_name === "Human Input") {
                            return (
                              <div
                                className="space-y-5 bg-background mb-4 w-full animate-fade-in animate-once animate-delay-300"
                                key={index}
                              >
                                <div className="transform transition-transform duration-300 hover:scale-105 animate-fade-right animate-once animate-duration-500">
                                  <div className="markdown-container text-base leading-7 break-words p-2">
                                    <Markdown
                                      remarkPlugins={[remarkBreaks]}
                                      rehypePlugins={[rehypeRaw]}
                                      components={{
                                        code({ className, children, ...props }) {
                                          return (
                                            <pre className="code-block">
                                              <code className={className} {...props}>
                                                {children}
                                              </code>
                                            </pre>
                                          );
                                        },
                                        h1: ({ children }) => (
                                          <h1 className="text-2xl font-bold mt-6 mb-4">
                                            {children}
                                          </h1>
                                        ),
                                        h2: ({ children }) => (
                                          <h2 className="text-xl font-bold mt-5 mb-3">
                                            {children}
                                          </h2>
                                        ),
                                        h3: ({ children }) => (
                                          <h3 className="text-lg font-bold mt-4 mb-2">
                                            {children}
                                          </h3>
                                        ),
                                        h4: ({ children }) => (
                                          <h4 className="text-base font-bold mt-3 mb-2">
                                            {children}
                                          </h4>
                                        ),
                                        h5: ({ children }) => (
                                          <h5 className="text-sm font-bold mt-3 mb-1">
                                            {children}
                                          </h5>
                                        ),
                                        h6: ({ children }) => (
                                          <h6 className="text-xs font-bold mt-3 mb-1">
                                            {children}
                                          </h6>
                                        ),
                                        p: ({ children }) => (
                                          <p className="mb-4">{children}</p>
                                        ),
                                        a: ({ href, children }) => (
                                          <a
                                            href={href}
                                            className="text-primary hover:underline"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                          >
                                            {children}
                                          </a>
                                        ),
                                        ul: ({ children }) => (
                                          <ul className="list-disc pl-6 mb-4">
                                            {children}
                                          </ul>
                                        ),
                                        ol: ({ children }) => (
                                          <ol className="list-decimal pl-6 mb-4">
                                            {children}
                                          </ol>
                                        ),
                                        li: ({ children }) => (
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
                                      className={`w-full max-h-[20vh] focus:shadow-lg resize-none pb-5 transition-all duration-300 ${humanInputValue
                                        ? "border-primary border-2"
                                        : "border"
                                        }`}
                                      style={{
                                        overflowY: rows >= 12 ? "auto" : "hidden",
                                      }}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                          if (e.shiftKey) {
                                            setHumanInputValue((prev) => prev + "\n");
                                          } else {
                                            e.preventDefault();
                                            if (humanInputValue.length > 0) {
                                              handleHumanInputSubmit();
                                            }
                                          }
                                        }
                                      }}
                                    />
                                    {humanInputValue.trim().length > 0 && (
                                      <>
                                        <Button
                                          size="icon"
                                          className={`absolute right-2 top-2 transition-all duration-300 ${animateSubmit
                                            ? "scale-90"
                                            : "hover:scale-110"
                                            }`}
                                          onClick={handleHumanInputSubmit}
                                        >
                                          <Send size={20} absoluteStrokeWidth />
                                        </Button>
                                        <p className="text-[13px] text-muted-foreground absolute right-3 bottom-3 pointer-events-none animate-fade-in animate-duration-300">
                                          press shift + enter to go to new line
                                        </p>
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          }

                          return (
                            <Card
                              key={index}
                              className="p-4 bg-background mb-4 w-[98%] transition-all duration-500 ease-in-out transform hover:shadow-md hover:-translate-y-1 animate-fade-up animate-once animate-duration-700"
                              style={{ animationDelay: `${index * 300}ms` }}
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
                                            <Markdown rehypePlugins={[rehypeRaw]}>
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
                                      onClick={() =>
                                        handleOutputSelection(
                                          outputsList.findIndex(
                                            (item) =>
                                              item.agent ===
                                              systemMessage.agent_name
                                          )
                                        )
                                      }
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
                        }
                        )}
                        {message.data &&
                          message.data.find(
                            (systemMessage) =>
                              systemMessage.agent_name === "Orchestrator" &&
                              systemMessage?.output
                          ) && (
                            <div className="space-y-3 animate-fade-in animate-once animate-delay-700 animate-duration-1000 w-[98%]">
                              {message.data.find(
                                (systemMessage) =>
                                  systemMessage.agent_name === "Orchestrator"
                              )?.status_code === 200 ? (
                                <div
                                  onClick={() =>
                                    handleOutputSelection(
                                      outputsList.findIndex(
                                        (item) => item.agent === "Orchestrator"
                                      )
                                    )
                                  }
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
                                  errorMessage={
                                    message.data.find(
                                      (systemMessage) =>
                                        systemMessage.agent_name ===
                                        "Orchestrator"
                                    )?.output
                                  }
                                />
                              )}
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
          className={`border-2 rounded-xl w-[50%] flex flex-col h-[95%] justify-between items-center transition-all duration-700 ease-in-out ${animateIframeEntry
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
              className={`w-full aspect-video bg-transparent transition-all duration-700 ${isIframeLoading
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
                className={`p-3 w-full h-full transition-all duration-500 ${animateOutputEntry
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
