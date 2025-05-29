import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
   children: ReactNode;
   fallback?: ReactNode;
}

interface State {
   hasError: boolean;
   error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
   public state: State = {
      hasError: false,
      error: null,
   };

   public static getDerivedStateFromError(error: Error): State {
      return { hasError: true, error };
   }

   public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
      console.error("MCP Error:", error, errorInfo);
   }

   public render() {
      if (this.state.hasError) {
         return (
            this.props.fallback || (
               <div className="p-8 space-y-4">
                  <div className="p-4 rounded-lg bg-red-500/20 border border-red-500/50">
                     <h2 className="text-xl font-semibold text-red-400 mb-2">
                        Something went wrong
                     </h2>
                     <p className="text-gray-400">
                        {this.state.error?.message ||
                           "An unexpected error occurred"}
                     </p>
                     <button
                        className="mt-4 px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors"
                        onClick={() =>
                           this.setState({ hasError: false, error: null })
                        }
                     >
                        Try again
                     </button>
                  </div>
               </div>
            )
         );
      }

      return this.props.children;
   }
}

export default ErrorBoundary;
