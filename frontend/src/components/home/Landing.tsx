import {EXAMPLES} from "@/constants/Landing";
import {setMessages} from "@/dataStore/messagesSlice";
import {ChatListPageProps} from "@/types/chatTypes";
import {Book, Send, TextSelect} from "lucide-react";
import {useEffect, useRef, useState} from "react";
import {useDispatch} from "react-redux";
import favicon from "../../assets/Favicon-contexton.svg";
import {Button} from "../ui/button";
import {Card, CardDescription, CardHeader, CardTitle} from "../ui/card";
import {Textarea} from "../ui/textarea";

const Landing = ({setIsLoading}: ChatListPageProps) => {
  const dispatch = useDispatch();

  const [goal, setGoal] = useState<string>("");
  const [animateSubmit, setAnimateSubmit] = useState<boolean>(false);
  const [rows, setRows] = useState(4);
  const [examplesVisible, setExamplesVisible] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Trigger examples animation after component mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setExamplesVisible(true);
    }, 600); // Delay examples appearance for a staggered effect

    return () => clearTimeout(timer);
  }, []);

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

  const handleSubmit = () => {
    if (!goal.trim()) return;

    // Trigger the send button animation
    setAnimateSubmit(true);
    setTimeout(() => setAnimateSubmit(false), 300);

    dispatch(
      setMessages([
        {
          role: "user",
          prompt: goal,
          sent_at: new Date().toISOString(),
        },
        {
          role: "system",
          data: [],
        },
      ])
    );

    setIsLoading(true);
    setGoal("");
  };

  const handleExampleClick = (example: string) => {
    // Animate the selected example
    setGoal(example);
    if (textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.classList.add("animate-pulse");
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.classList.remove("animate-pulse");
        }
      }, 500);
    }
    adjustHeight();
  };

  return (
    <div className="w-[60%] h-[80vh] flex flex-col items-center space-y-10 animate-fade-in pb-10">
      <div className="flex flex-col items-center space-y-7 animate-fade-down animate-once animate-duration-500 animate-ease-in-out">
        <img
          src={favicon}
          width="100px"
          className="animate-spin-slow animate-once animate-duration-[1.5s] animate-ease-out"
        />
        <div className="flex flex-col justify-center items-center space-y-3">
          <p className="text-4xl bg-clip-text text-transparent bg-gradient-to-r from-primary to-primary/70 animate-gradient">
            Provide a task to CortexON
          </p>
        </div>
      </div>
      <div className="relative w-[90%] transition-all duration-300 hover:scale-[1.01] focus-within:scale-[1.01]">
        <Textarea
          ref={textareaRef}
          draggable={false}
          placeholder="Enter how can CortexON help you..."
          rows={rows}
          value={goal}
          onChange={(e) => {
            setGoal(e.target.value);
            adjustHeight();
          }}
          className={`w-full max-h-[20vh] focus:shadow-lg resize-none pb-5 transition-all duration-300 ${
            goal ? "border-primary border-2" : "border"
          }`}
          style={{
            overflowY: rows >= 12 ? "auto" : "hidden",
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              if (e.shiftKey) {
                // Shift+Enter - insert a new line
                setGoal((prev) => prev + "\n");
              } else {
                // Just Enter - submit the form
                e.preventDefault(); // Prevent default newline behavior
                if (goal.length > 0) {
                  handleSubmit();
                }
              }
            }
          }}
        />
        {goal.trim().length > 0 && (
          <Button
            size="icon"
            className={`absolute right-2 top-2 transition-all duration-300 ${
              animateSubmit ? "scale-90" : "hover:scale-110"
            }`}
            onClick={handleSubmit}
          >
            <Send
              size={20}
              absoluteStrokeWidth
              className={`transition-all duration-300 ${
                animateSubmit ? "animate-ping animate-once" : ""
              }`}
            />
          </Button>
        )}
        {goal.trim().length > 0 && (
          <p className="text-[13px] text-muted-foreground absolute right-3 bottom-3 pointer-events-none animate-fade-in animate-duration-300">
            press shift + enter to go to new line
          </p>
        )}
      </div>
      <div
        className={`space-y-3 w-full pb-4 transition-opacity duration-500 ease-in-out ${
          examplesVisible ? "opacity-100" : "opacity-0"
        }`}
      >
        <p className="text-lg text-muted-foreground flex gap-2 px-2 items-center">
          <Book size={20} absoluteStrokeWidth />
          Try these examples...
        </p>
        <div className="flex gap-2">
          {EXAMPLES.map((example, idx) => (
            <Card
              key={idx}
              className="w-[33%] hover:cursor-pointer transition-all duration-300 hover:shadow-md hover:border-primary/50 hover:-translate-y-1"
              style={{
                animationDelay: `${idx * 150}ms`,
                animationFillMode: "backwards",
              }}
              onClick={() => handleExampleClick(example.prompt)}
            >
              <CardHeader className="space-y-2">
                <TextSelect size={20} absoluteStrokeWidth />
                <CardTitle>{example.title}</CardTitle>
                <CardDescription>{example.description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Landing;
