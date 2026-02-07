"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { chatApi, uploadApi, type ChatMessage, type Facility } from "@/lib/api";

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onDataLoad?: (facilities: Facility[], filename: string) => void;
}

interface ChatSession {
  id: string;
  title: string;
  timestamp: string;
  messageCount: number;
  lastMessage?: string;
}

const API_KEY_STORAGE_KEY = "tessera_ai_api_key";
const PROVIDER_STORAGE_KEY = "tessera_ai_provider";
const SESSIONS_STORAGE_KEY = "tessera_chat_sessions";

type AIProvider = "openai" | "gemini";

// Helper functions for session management
const getSavedSessions = (): ChatSession[] => {
  try {
    const saved = localStorage.getItem(SESSIONS_STORAGE_KEY);
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
};

const saveSession = (session: ChatSession) => {
  const sessions = getSavedSessions();
  const existingIndex = sessions.findIndex((s) => s.id === session.id);

  if (existingIndex >= 0) {
    sessions[existingIndex] = session;
  } else {
    sessions.unshift(session);
  }

  localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
};

const deleteSession = (sessionId: string) => {
  const sessions = getSavedSessions().filter((s) => s.id !== sessionId);
  localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
};

const getRelativeTime = (timestamp: string): string => {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return then.toLocaleDateString();
};

export default function ChatPanel({
  isOpen,
  onClose,
  onDataLoad,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState<AIProvider>("openai");
  const [showApiKeyInput, setShowApiKeyInput] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  // Load saved sessions on mount
  useEffect(() => {
    setSessions(getSavedSessions());
  }, []);

  // Load API key and provider from localStorage on mount
  useEffect(() => {
    const storedKey = localStorage.getItem(API_KEY_STORAGE_KEY);
    const storedProvider = localStorage.getItem(
      PROVIDER_STORAGE_KEY,
    ) as AIProvider;

    if (storedKey) {
      setApiKey(storedKey);
    } else {
      setShowApiKeyInput(true);
    }

    if (
      storedProvider &&
      (storedProvider === "openai" || storedProvider === "gemini")
    ) {
      setProvider(storedProvider);
    }
  }, []);

  // Create new session on mount or when needed
  useEffect(() => {
    const initSession = async () => {
      try {
        const response = await chatApi.newSession();
        setSessionId(response.session_id);
      } catch (err) {
        console.error("Failed to create chat session:", err);
        setError("Failed to start chat session");
      }
    };

    if (!sessionId) {
      initSession();
    }
  }, [sessionId]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && !showApiKeyInput) {
      inputRef.current?.focus();
    }
  }, [isOpen, showApiKeyInput]);

  const handleSaveApiKey = useCallback(() => {
    if (apiKey.trim()) {
      localStorage.setItem(API_KEY_STORAGE_KEY, apiKey.trim());
      localStorage.setItem(PROVIDER_STORAGE_KEY, provider);
      setShowApiKeyInput(false);
      setError(null);
    }
  }, [apiKey, provider]);

  const handleClearApiKey = useCallback(() => {
    localStorage.removeItem(API_KEY_STORAGE_KEY);
    setApiKey("");
    setShowApiKeyInput(true);
  }, []);

  const handleUploadFile = useCallback(
    async (file: File) => {
      if (!file.name.endsWith(".csv") || !sessionId || !apiKey || isUploading)
        return;

      setIsUploading(true);
      setError(null);

      try {
        const response = await uploadApi.uploadRawCSV(file);

        if (response.success) {
          // Add a local message indicating upload
          const systemMsg: ChatMessage = {
            role: "assistant",
            content: `📁 **File Uploaded**: \`${file.name}\`\nI've received your dataset. I'll analyze its structure and help you map the columns for analysis.`,
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, systemMsg]);

          // Send a hidden instruction to the LLM
          await chatApi.sendMessage({
            session_id: sessionId,
            message: `[SYSTEM] User uploaded a new dataset: ${file.name}. Path: ${response.path}. Please analyze the dataset using the 'analyze_dataset' tool and guide the user through mapping the columns.`,
            api_key: apiKey,
            provider: provider,
          });

          // Trigger a refresh/response from the agent by sending another message or just waiting for the first one's response
          // Actually, the above sendMessage will get a response which we should handle
          const agentResponse = await chatApi.sendMessage({
            session_id: sessionId,
            message: `I've uploaded the file ${file.name}. What should I do next?`,
            api_key: apiKey,
            provider: provider,
          });

          const assistantMessage: ChatMessage = {
            role: "assistant",
            content: agentResponse.response,
            timestamp: agentResponse.timestamp,
          };

          setMessages((prev) => [...prev, assistantMessage]);
        }
      } catch (err) {
        setError("Failed to upload file");
        console.error(err);
      } finally {
        setIsUploading(false);
        setIsDragging(false);
      }
    },
    [sessionId, apiKey, isUploading, provider],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (apiKey && sessionId) {
        setIsDragging(true);
      }
    },
    [apiKey, sessionId],
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        handleUploadFile(file);
      }
    },
    [handleUploadFile],
  );

  const handleSendMessage = useCallback(async () => {
    if (!input.trim() || !sessionId || !apiKey || isLoading) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await chatApi.sendMessage({
        session_id: sessionId,
        message: userMessage.content,
        api_key: apiKey,
        provider: provider,
      });

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.response,
        timestamp: response.timestamp,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Save session metadata after each successful exchange
      if (sessionId) {
        const currentMessages = [...messages, userMessage, assistantMessage];
        const title =
          messages.length === 0
            ? userMessage.content.slice(0, 50)
            : sessions.find((s) => s.id === sessionId)?.title ||
              userMessage.content.slice(0, 50);

        saveSession({
          id: sessionId,
          title,
          timestamp: new Date().toISOString(),
          messageCount: currentMessages.length,
          lastMessage: assistantMessage.content.slice(0, 100),
        });

        // Update sessions state
        setSessions(getSavedSessions());
      }

      // Handle incoming data (e.g., from transform_dataset)
      if (
        response.data?.type === "standardized_dataset" &&
        response.data.facilities
      ) {
        console.log(
          "Received standardized dataset from chat:",
          response.data.facilities.length,
        );
        if (onDataLoad) {
          onDataLoad(response.data.facilities, "Chat Augmentation");
        }
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to send message";
      setError(errorMessage);

      // Check if it's an API key error
      if (errorMessage.includes("API key") || errorMessage.includes("401")) {
        setShowApiKeyInput(true);
      }
    } finally {
      setIsLoading(false);
    }
  }, [input, sessionId, apiKey, isLoading, messages, sessions]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    },
    [handleSendMessage],
  );

  const handleNewChat = useCallback(async () => {
    try {
      setMessages([]);
      const response = await chatApi.newSession();
      setSessionId(response.session_id);
      setError(null);
      setShowHistory(false);
    } catch (err) {
      console.error("Failed to create new session:", err);
    }
  }, []);

  const handleLoadSession = useCallback(async (sid: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // Load conversation history from backend
      const response = await chatApi.getHistory(sid);
      setMessages(response.messages);
      setSessionId(sid);
      setShowHistory(false);
    } catch (err) {
      console.error("Failed to load session:", err);
      setError("Failed to load conversation history");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleDeleteSession = useCallback(
    (sid: string, e: React.MouseEvent) => {
      e.stopPropagation();
      deleteSession(sid);
      setSessions(getSavedSessions());

      // If deleting current session, start a new one
      if (sid === sessionId) {
        handleNewChat();
      }
    },
    [sessionId, handleNewChat],
  );

  if (!isOpen) return null;

  return (
    <div
      className={`fixed bottom-4 right-4 w-96 h-[600px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden z-[3000] ${isDragging ? "ring-2 ring-indigo-500 shadow-indigo-200" : ""}`}
      onDragEnter={handleDragOver}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
            <svg
              className="w-5 h-5 text-indigo-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
          </div>
          <div>
            <h2 className="font-bold text-gray-800">Tessera Assistant</h2>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              <span className="text-[10px] text-gray-800 font-medium uppercase tracking-wider">
                AI Powered
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 text-gray-800">
          <button
            onClick={handleNewChat}
            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
            title="New conversation"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
          </button>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`p-1.5 rounded-lg transition-colors ${showHistory ? "bg-white/20" : "hover:bg-white/10"}`}
            title="Conversation history"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </button>
          <button
            onClick={() => setShowApiKeyInput(!showApiKeyInput)}
            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
            title="API Key settings"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
              />
            </svg>
          </button>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* API Key Input */}
      {showApiKeyInput && (
        <div className="p-4 bg-amber-50 border-b border-amber-100 animate-in slide-in-from-top duration-300">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-amber-800">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
                />
              </svg>
              <span className="text-xs font-bold uppercase tracking-wider">
                Settings
              </span>
            </div>
            <div className="flex bg-white rounded-lg p-0.5 border border-amber-200">
              <button
                onClick={() => setProvider("openai")}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition-all ${provider === "openai" ? "bg-amber-600 text-white shadow-sm" : "text-amber-600 hover:bg-amber-50"}`}
              >
                OpenAI
              </button>
              <button
                onClick={() => setProvider("gemini")}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition-all ${provider === "gemini" ? "bg-amber-600 text-white shadow-sm" : "text-amber-600 hover:bg-amber-50"}`}
              >
                Gemini
              </button>
            </div>
          </div>
          <label className="block text-sm font-medium text-amber-800 mb-2">
            {provider === "openai" ? "OpenAI API Key" : "Google AI API Key"}
          </label>
          <div className="flex gap-2">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider === "openai" ? "sk-..." : "AIza..."}
              className="flex-1 px-3 py-2 text-sm border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white"
            />
            <button
              onClick={handleSaveApiKey}
              disabled={!apiKey.trim()}
              className="px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save
            </button>
          </div>
          {apiKey && (
            <button
              onClick={handleClearApiKey}
              className="mt-2 text-xs text-amber-700 hover:underline"
            >
              Clear saved key
            </button>
          )}
          <p className="mt-2 text-xs text-amber-700">
            Your API key is stored locally in your browser.
          </p>
        </div>
      )}

      {/* Messages or History View */}
      <div
        className={`flex-1 overflow-y-auto p-4 space-y-4 relative ${isDragging ? "bg-indigo-50/50" : ""}`}
      >
        {/* History View */}
        {showHistory ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-gray-800">Chat History</h3>
              <span className="text-xs text-gray-500">
                {sessions.length} conversations
              </span>
            </div>

            {sessions.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-3">
                  <svg
                    className="w-6 h-6 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
                <p className="text-gray-500 text-sm">No conversations yet</p>
                <p className="text-gray-400 text-xs mt-1">
                  Start a new chat to begin
                </p>
              </div>
            ) : (
              sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => handleLoadSession(session.id)}
                  className={`w-full text-left p-3 rounded-lg border transition-all hover:shadow-md ${
                    session.id === sessionId
                      ? "border-indigo-300 bg-indigo-50"
                      : "border-gray-200 bg-white hover:border-indigo-200"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {session.title}
                      </p>
                      {session.lastMessage && (
                        <p className="text-xs text-gray-500 truncate mt-1">
                          {session.lastMessage}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-xs text-gray-400">
                          {getRelativeTime(session.timestamp)}
                        </span>
                        <span className="text-xs text-gray-400">
                          {session.messageCount} messages
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDeleteSession(session.id, e)}
                      className="p-1 hover:bg-red-100 rounded transition-colors flex-shrink-0"
                      title="Delete conversation"
                    >
                      <svg
                        className="w-4 h-4 text-red-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                </button>
              ))
            )}
          </div>
        ) : (
          <>
            {/* Drag and Drop */}
            {isDragging && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-indigo-50/80 pointer-events-none border-2 border-dashed border-indigo-400 m-2 rounded-xl">
                <div className="text-center">
                  <svg
                    className="w-12 h-12 text-indigo-500 mx-auto mb-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                  <p className="text-indigo-700 font-medium">
                    Drop CSV to analyze
                  </p>
                </div>
              </div>
            )}

            {/* Empty State */}
            {messages.length === 0 && !showApiKeyInput && (
              <div className="text-center py-8">
                <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center mx-auto mb-3">
                  <svg
                    className="w-6 h-6 text-indigo-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                </div>
                <p className="text-gray-600 text-sm font-medium">
                  How can I help?
                </p>
                <p className="text-gray-400 text-xs mt-1">
                  Ask about facilities, population, or coverage
                </p>
                <div className="mt-4 space-y-2">
                  {[
                    "Which facility serves location 28.6, 77.2?",
                    "Show top 5 facilities by population",
                    "What's the coverage summary?",
                  ].map((suggestion, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(suggestion)}
                      className="block w-full text-left px-3 py-2 text-xs text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white rounded-br-md"
                      : "bg-gray-100 text-gray-800 rounded-bl-md"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <div className="text-sm markdown-body">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          ul: ({ node, ...props }) => (
                            <ul className="list-disc pl-4 my-1" {...props} />
                          ),
                          ol: ({ node, ...props }) => (
                            <ol className="list-decimal pl-4 my-1" {...props} />
                          ),
                          li: ({ node, ...props }) => (
                            <li className="my-0.5" {...props} />
                          ),
                          p: ({ node, ...props }) => (
                            <p className="mb-2 last:mb-0" {...props} />
                          ),
                          strong: ({ node, ...props }) => (
                            <strong className="font-semibold" {...props} />
                          ),
                          a: ({ node, ...props }) => (
                            <a
                              className="text-blue-600 hover:underline"
                              target="_blank"
                              rel="noopener noreferrer"
                              {...props}
                            />
                          ),
                          code: ({ node, ...props }) => (
                            <code
                              className="bg-gray-200 px-1 py-0.5 rounded text-xs font-mono"
                              {...props}
                            />
                          ),
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
                  <div className="flex gap-1">
                    <span
                      className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: "0ms" }}
                    />
                    <span
                      className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: "150ms" }}
                    />
                    <span
                      className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: "300ms" }}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Uploading Indicator */}
            {isUploading && (
              <div className="flex justify-start">
                <div className="bg-indigo-50 border border-indigo-100 px-4 py-3 rounded-2xl rounded-bl-md flex items-center gap-3">
                  <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-xs text-indigo-700 font-medium">
                    Uploading dataset...
                  </span>
                </div>
              </div>
            )}

            {/* Error Display */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200 bg-gray-50 text-gray-800">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              apiKey ? "Ask about your data..." : "Enter API key first..."
            }
            disabled={!apiKey || isLoading || showHistory}
            className="flex-1 px-4 py-2.5 text-sm border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSendMessage}
            disabled={!input.trim() || !apiKey || isLoading || showHistory}
            className="px-4 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
