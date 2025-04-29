import {useRef, useState} from "react";
import Markdown from "react-markdown";
import {Prism as SyntaxHighlighter} from "react-syntax-highlighter";
import {vscDarkPlus} from "react-syntax-highlighter/dist/esm/styles/prism";
import rehypeRaw from "rehype-raw";
import remarkBreaks from "remark-breaks";

export const CodeBlock = ({content}: {content: string}) => {
  const codeBlock = content.includes("content='")
    ? content.split("content='")[1]
    : content;

  const [isCopied, setIsCopied] = useState(false);
  const codeRef = useRef<HTMLDivElement>(null);

  const handleCopyClick = () => {
    if (codeRef.current) {
      // Find all code blocks and join their text content
      const codeElements = codeRef.current.querySelectorAll('pre code');
      let textToCopy = '';
      
      if (codeElements.length > 0) {
        // Get text from syntax highlighted blocks
        codeElements.forEach(el => {
          textToCopy += el.textContent + '\n\n';
        });
      } else {
        // Fallback to all text content
        textToCopy = codeRef.current.innerText;
      }
      
      navigator.clipboard
        .writeText(textToCopy.trim())
        .then(() => {
          setIsCopied(true);
          // Add a visual pulse effect
          if (codeRef.current) {
            codeRef.current.classList.add("copy-pulse");
            setTimeout(() => {
              if (codeRef.current) {
                codeRef.current.classList.remove("copy-pulse");
              }
            }, 1000);
          }
          setTimeout(() => setIsCopied(false), 2000);
        })
        .catch((err) => console.error("Failed to copy text: ", err));
    }
  };

  return (
    <div className="relative w-full overflow-x-auto scrollbar-thin text-sm leading-6 bg-zinc-900 rounded-lg shadow-md p-4">
      <button
        onClick={handleCopyClick}
        className="absolute top-4 right-4 bg-zinc-800 text-zinc-300 px-3 py-1 rounded-md text-xs font-medium hover:bg-zinc-700 transition-colors duration-200 z-10 border border-zinc-700 shadow-sm flex items-center gap-1"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {isCopied ? (
            <>
              <polyline points="20 6 9 17 4 12"></polyline>
            </>
          ) : (
            <>
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </>
          )}
        </svg>
        {isCopied ? "Copied!" : "Copy"}
      </button>
      <div ref={codeRef} className="markdown-container text-zinc-200">
        <Markdown
          children={codeBlock.replace(/\\n/g, "\n")}
          rehypePlugins={[rehypeRaw]}
          remarkPlugins={[remarkBreaks]}
          components={{
            code(props) {
              const {children, className, ...rest} = props;
              const match = /language-(\w+)/.exec(className || "");
              return match ? (
                <SyntaxHighlighter
                  PreTag="div"
                  language={match[1] || "python"}
                  style={vscDarkPlus}
                  showLineNumbers={true}
                  wrapLongLines={false}
                  className="animate-fade-in w-full overflow-x-auto scrollbar-thin rounded-md my-3 shadow-inner border border-zinc-800"
                  customStyle={{
                    padding: '1.25rem',
                    backgroundColor: '#18181b', // zinc-900
                    fontSize: '0.9rem',
                    lineHeight: '1.5',
                  }}
                >
                  {String(children).replace(/\n$/, "")}
                </SyntaxHighlighter>
              ) : (
                <code {...rest} className={`${className} px-1.5 py-0.5 rounded-sm bg-zinc-800 font-mono text-zinc-200`}>
                  {children}
                </code>
              );
            },
            // Add heading styles
            h1: ({children}) => (
              <h1 className="text-2xl font-bold mt-6 mb-3 text-zinc-100 border-b border-zinc-700 pb-2">{children}</h1>
            ),
            h2: ({children}) => (
              <h2 className="text-xl font-bold mt-5 mb-3 text-zinc-100 border-b border-zinc-700 pb-2 flex items-center gap-2">
                {children}
              </h2>
            ),
            h3: ({children}) => (
              <h3 className="text-lg font-bold mt-4 mb-2 text-zinc-200">{children}</h3>
            ),
            // Add paragraph styles
            p: ({children}) => (
              <p className="my-3 text-zinc-300 leading-relaxed">{children}</p>
            ),
            // Style output code blocks
            pre: ({children}) => (
              <pre className="bg-zinc-800 p-4 rounded-md my-3 text-zinc-200 overflow-x-auto border border-zinc-700 shadow-sm font-mono text-sm">{children}</pre>
            ),
            // Style emojis and status indicators
            strong: ({children}) => {
              const text = String(children);
              if (text.includes("✅")) {
                return <strong className="font-semibold text-green-400">{children}</strong>;
              } else if (text.includes("❌")) {
                return <strong className="font-semibold text-red-400">{children}</strong>;
              }
              return <strong className="font-semibold text-zinc-100">{children}</strong>;
            },
            // Style links
            a: ({children, href}) => (
              <a 
                href={href} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="text-blue-400 hover:text-blue-300 underline decoration-dotted underline-offset-2 transition-colors duration-200"
              >
                {children}
              </a>
            ),
            // Style lists
            ul: ({children}) => (
              <ul className="list-disc pl-6 my-3 space-y-1 text-zinc-300">{children}</ul>
            ),
            ol: ({children}) => (
              <ol className="list-decimal pl-6 my-3 space-y-1 text-zinc-300">{children}</ol>
            ),
            li: ({children}) => (
              <li className="mb-1">{children}</li>
            ),
          }}
        />
      </div>
    </div>
  );
};
