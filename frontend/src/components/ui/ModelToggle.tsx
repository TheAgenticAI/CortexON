import { useDispatch, useSelector } from "react-redux";
import { RootState } from "@/dataStore/store";
import { setModelPreference } from "@/dataStore/modelPreferenceSlice";
import { useSetModelPreferenceMutation } from "@/services/modelPreferenceApi";
import { useEffect, useState } from "react";

export default function ModelToggle() {
  const dispatch = useDispatch();
  const modelPreference = useSelector((state: RootState) => state.modelPreference.preference);
  const [setModelPreferenceApi] = useSetModelPreferenceMutation();
  const [isAnthropicSelected, setIsAnthropicSelected] = useState(modelPreference === "Anthropic");

  const toggleModel = async () => {
    const newPreference = isAnthropicSelected ? "OpenAI" : "Anthropic";
    setIsAnthropicSelected(!isAnthropicSelected);
    
    try {
      // Update UI immediately
      dispatch(setModelPreference(newPreference));
      
      // Call API to update backend
      await setModelPreferenceApi(newPreference).unwrap();
    } catch (error) {
      console.error("Failed to update model preference:", error);
      // Revert UI on error
      setIsAnthropicSelected(isAnthropicSelected);
      dispatch(setModelPreference(isAnthropicSelected ? "Anthropic" : "OpenAI"));
    }
  };

  // Ensure UI reflects the redux state
  useEffect(() => {
    setIsAnthropicSelected(modelPreference === "Anthropic");
  }, [modelPreference]);

  return (
    <div className="flex items-center space-x-3 p-2 border rounded-lg bg-slate-50">
      <span className={isAnthropicSelected ? "text-purple-600 font-bold" : "text-gray-500"}>
        Claude
      </span>
      
      {/* Simple toggle switch built with CSS */}
      <button
        onClick={toggleModel}
        className={`relative inline-flex items-center h-7 rounded-full w-12 transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${
          isAnthropicSelected ? "bg-purple-600" : "bg-blue-600"
        }`}
      >
        <span
          className={`inline-block w-5 h-5 transform bg-white rounded-full shadow-md transition-transform ${
            isAnthropicSelected ? "translate-x-1" : "translate-x-6"
          }`}
        />
      </button>
      
      <span className={!isAnthropicSelected ? "text-blue-600 font-bold" : "text-gray-500"}>
        GPT-4o
      </span>
    </div>
  );
} 