import {
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Component,
  Globe,
  SquareCode,
  SquareSlash,
  X,
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
import {
  AgentOutput,
  ChatListPageProps,
  Message,
  SystemMessage,
} from "@/types/chatTypes";
import {useDispatch, useSelector} from "react-redux";
import useWebSocket, {ReadyState} from "react-use-websocket";
import {Button} from "../ui/button";
import {Card} from "../ui/card";
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
  // Modify your outputs state to use a map structure for better tracking
  const [outputsList, setOutputsList] = useState<AgentOutput[]>([]);
  const [currentOutput, setCurrentOutput] = useState<number | null>(null);
  // Add animation state for output panel
  const [animateOutputEntry, setAnimateOutputEntry] = useState<boolean>(false);

  // Create a ref for the scroll container
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messages = useSelector(
    (state: RootState) => state.messagesState.messages
  );
  const dispatch = useDispatch();

  // Create another ref to track the previous messages length
  const prevMessagesLengthRef = useRef(0);
  const prevSystemMessageLengthRef = useRef(0);

  const {sendMessage, lastJsonMessage, readyState} = useWebSocket(
    VITE_WEBSOCKET_URL,
    {
      onOpen: () => {
        if (
          messages.length > 0 &&
          messages[0]?.prompt &&
          messages[0].prompt.length > 0
        ) {
          sendMessage(messages[0].prompt);
        }
      },
      onError: () => {
        setIsLoading(false);
        console.log("Error connecting to webSocket.");
      },
      onClose: () => {
        setIsLoading(false);
        console.log("Websocket connection closed.");
      },
      reconnectAttempts: 3,
      retryOnError: true,
    }
  );

  const scrollToBottom = (smooth = true) => {
    if (scrollAreaRef.current) {
      // Get the actual scrollable div inside the ScrollArea component
      const scrollableDiv = scrollAreaRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (scrollableDiv) {
        // Find the last message element to scroll to
        const lastMessageElement = scrollAreaRef.current.querySelector(
          ".space-y-4 > div:last-child"
        );

        if (lastMessageElement) {
          // Use scrollIntoView for smooth scrolling behavior
          lastMessageElement.scrollIntoView({
            behavior: smooth ? "smooth" : "auto",
            block: "end",
          });
        } else {
          // Fallback to traditional scrollTop if element not found
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

    dispatch(
      setMessages((prev: Message[]) => {
        const lastMessage = prev[prev.length - 1];
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
          } = lastJsonMessage as SystemMessage;

          // Update live URL if provided
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

          // Find the agent name in the last message data and update the fields
          const agentIndex = lastMessageData.findIndex(
            (agent) => agent.agent_name === agent_name
          );

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
            lastMessageData[agentIndex] = {
              agent_name,
              instructions,
              steps: filteredSteps,
              output,
              status_code,
              live_url,
            };
          } else {
            lastMessageData.push({
              agent_name,
              instructions,
              steps,
              output,
              status_code,
              live_url,
            });
          }

          if (output && output.length > 0 && agent_name !== "Web Surfer") {
            // Only mark as complete for Orchestrator
            if (agent_name === "Orchestrator") {
              setIsLoading(false);
            }

            if (status_code === 200) {
              setOutputsList((prevList) => {
                // Check if this agent already has an output
                const existingIndex = prevList.findIndex(
                  (item) => item.agent === agent_name
                );

                let newList;
                let newOutputIndex; // Track the index of the new/updated output

                if (existingIndex >= 0) {
                  // Update existing output
                  newList = [...prevList];
                  newList[existingIndex] = {agent: agent_name, output};
                  newOutputIndex = existingIndex;
                } else {
                  // Add new output
                  newList = [...prevList, {agent: agent_name, output}];
                  newOutputIndex = newList.length - 1;
                }

                // Always set the most recent output as current
                // Use setTimeout to ensure state updates properly
                setAnimateOutputEntry(false);

                // After a short delay, change the output and trigger entry animation
                setTimeout(() => {
                  setCurrentOutput(newOutputIndex);
                  setAnimateOutputEntry(true);
                }, 300);

                return newList;
              });
            }
          }

          // Create a new array to ensure state update
          return [
            ...prev.slice(0, prev.length - 1),
            {
              ...lastMessage,
              data: [...lastMessageData],
            },
          ];
        }
        return [...prev];
      })
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastJsonMessage, messages.length, setIsLoading, setMessages]);

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

  // Function to handle output selection with animation
  const handleOutputSelection = (index: number) => {
    // If we're already showing this output, don't do anything
    if (currentOutput === index) return;

    // If we're switching from one output to another, animate the transition
    if (currentOutput !== null) {
      // Set animation flag to false first (to trigger exit animation)
      setAnimateOutputEntry(false);

      // After a short delay, change the output and trigger entry animation
      setTimeout(() => {
        setCurrentOutput(index);
        setAnimateOutputEntry(true);
      }, 300); // Match this with CSS transition duration
    } else {
      // If we're showing an output for the first time
      setCurrentOutput(index);
      setAnimateOutputEntry(true);
    }
  };

  useEffect(() => {
    // Only scroll if messages have been added
    const currentMessagesLength = messages.length;
    let shouldScroll = false;

    if (currentMessagesLength > prevMessagesLengthRef.current) {
      shouldScroll = true;
    } else if (
      currentMessagesLength > 0 &&
      messages[currentMessagesLength - 1].role === "system"
    ) {
      // Check if system message data has changed
      const systemMessage = messages[currentMessagesLength - 1];
      const currentSystemDataLength = systemMessage.data?.length || 0;

      if (currentSystemDataLength > prevSystemMessageLengthRef.current) {
        shouldScroll = true;
      }

      // Update system message data length ref
      prevSystemMessageLengthRef.current = currentSystemDataLength;
    }

    // Update messages length ref
    prevMessagesLengthRef.current = currentMessagesLength;

    // Scroll with a slight delay to ensure content has rendered
    if (shouldScroll) {
      setTimeout(scrollToBottom, 100);
    }
  }, [messages]);

  // Additional useEffect to handle scrolling on initial load
  useEffect(() => {
    // Initial scroll without smooth behavior for immediate positioning
    scrollToBottom(false);

    // Add window resize listener to maintain scroll position
    const handleResize = () => {
      scrollToBottom(false);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  // Reset iframe animation flag when iframe is hidden
  useEffect(() => {
    if (!liveUrl) {
      setAnimateIframeEntry(false);
    }
  }, [liveUrl]);

  // Reset output animation flag when output is hidden
  useEffect(() => {
    if (currentOutput === null) {
      setAnimateOutputEntry(false);
    }
  }, [currentOutput]);

  window.addEventListener("message", function (event) {
    if (event.data === "browserbase-disconnected") {
      console.log("Message received from iframe:", event.data);
      // Handle the disconnection logic here
      setLiveUrl("");
    }
  });

  // Calculate width based on whether liveUrl or output is present
  const chatContainerWidth = liveUrl || currentOutput !== null ? "50%" : "65%";

  // Calculate animation classes for output panel
  const outputPanelClasses = `border-2 rounded-xl w-[50%] flex flex-col h-[95%] justify-between items-center transition-all duration-700 ease-in-out ${
    animateOutputEntry
      ? "opacity-100 translate-x-0 animate-fade-in animate-once animate-duration-1000"
      : "opacity-0 translate-x-2"
  }`;

  return (
    <div className="w-full h-full flex justify-center items-center px-4 gap-4">
      <div
        className="h-full flex flex-col items-center space-y-10 pt-8 transition-all duration-500 ease-in-out"
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
                          ) : (
                            <Card
                              key={index}
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
                                  (systemMessage.agent_name !== "Web Surfer" ? (
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
                        )}
                        {/* Add output of the orchestrator */}
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
                setTimeout(() => setIsIframeLoading(false), 300); // Delay to show transition
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
          <div className="bg-secondary h-[7vh] flex w-full rounded-b-xl justify-end px-4 animate-fade-up animate-once animate-duration-700">
            {/* Browser session footer */}
          </div>
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
