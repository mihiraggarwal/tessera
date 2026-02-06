'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi, type ChatMessage } from '@/lib/api';

interface ChatPanelProps {
    isOpen: boolean;
    onClose: () => void;
}

const API_KEY_STORAGE_KEY = 'tessera_ai_api_key';
const PROVIDER_STORAGE_KEY = 'tessera_ai_provider';

type AIProvider = 'openai' | 'gemini';

export default function ChatPanel({ isOpen, onClose }: ChatPanelProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [apiKey, setApiKey] = useState('');
    const [provider, setProvider] = useState<AIProvider>('openai');
    const [showApiKeyInput, setShowApiKeyInput] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Load API key and provider from localStorage on mount
    useEffect(() => {
        const storedKey = localStorage.getItem(API_KEY_STORAGE_KEY);
        const storedProvider = localStorage.getItem(PROVIDER_STORAGE_KEY) as AIProvider;

        if (storedKey) {
            setApiKey(storedKey);
        } else {
            setShowApiKeyInput(true);
        }

        if (storedProvider && (storedProvider === 'openai' || storedProvider === 'gemini')) {
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
                console.error('Failed to create chat session:', err);
                setError('Failed to start chat session');
            }
        };

        if (!sessionId) {
            initSession();
        }
    }, [sessionId]);

    // Scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
        setApiKey('');
        setShowApiKeyInput(true);
    }, []);

    const handleSendMessage = useCallback(async () => {
        if (!input.trim() || !sessionId || !apiKey || isLoading) return;

        const userMessage: ChatMessage = {
            role: 'user',
            content: input.trim(),
            timestamp: new Date().toISOString(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
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
                role: 'assistant',
                content: response.response,
                timestamp: response.timestamp,
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
            setError(errorMessage);

            // Check if it's an API key error
            if (errorMessage.includes('API key') || errorMessage.includes('401')) {
                setShowApiKeyInput(true);
            }
        } finally {
            setIsLoading(false);
        }
    }, [input, sessionId, apiKey, isLoading]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    }, [handleSendMessage]);

    const handleNewChat = useCallback(async () => {
        try {
            setMessages([]);
            const response = await chatApi.newSession();
            setSessionId(response.session_id);
            setError(null);
        } catch (err) {
            console.error('Failed to create new session:', err);
        }
    }, []);

    if (!isOpen) return null;

    return (
        <div className="fixed bottom-4 right-4 w-96 h-[600px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden z-[3000]">
            {/* Header */}
            <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                        <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                    </div>
                    <div>
                        <h3 className="font-semibold text-gray-900 text-sm">Tessera Assistant</h3>
                        <p className="text-xs text-gray-500">Ask about facility data</p>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={handleNewChat}
                        className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                        title="New conversation"
                    >
                        <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                    </button>
                    <button
                        onClick={() => setShowApiKeyInput(!showApiKeyInput)}
                        className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                        title="API Key settings"
                    >
                        <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                        </svg>
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                    >
                        <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* API Key Input */}
            {showApiKeyInput && (
                <div className="p-4 bg-amber-50 border-b border-amber-200">
                    <div className="mb-3">
                        <label className="block text-sm font-medium text-amber-800 mb-2">
                            AI Provider
                        </label>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setProvider('openai')}
                                className={`flex-1 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${provider === 'openai'
                                    ? 'bg-amber-600 text-white'
                                    : 'bg-white text-amber-800 border border-amber-300 hover:bg-amber-100'
                                    }`}
                            >
                                OpenAI
                            </button>
                            <button
                                onClick={() => setProvider('gemini')}
                                className={`flex-1 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${provider === 'gemini'
                                    ? 'bg-amber-600 text-white'
                                    : 'bg-white text-amber-800 border border-amber-300 hover:bg-amber-100'
                                    }`}
                            >
                                Gemini
                            </button>
                        </div>
                    </div>
                    <label className="block text-sm font-medium text-amber-800 mb-2">
                        {provider === 'openai' ? 'OpenAI API Key' : 'Google AI API Key'}
                    </label>
                    <div className="flex gap-2">
                        <input
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder={provider === 'openai' ? 'sk-...' : 'AIza...'}
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

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && !showApiKeyInput && (
                    <div className="text-center py-8">
                        <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center mx-auto mb-3">
                            <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                        </div>
                        <p className="text-gray-600 text-sm font-medium">How can I help?</p>
                        <p className="text-gray-400 text-xs mt-1">
                            Ask about facilities, population, or coverage
                        </p>
                        <div className="mt-4 space-y-2">
                            {[
                                "Which facility serves location 28.6, 77.2?",
                                "Show top 5 facilities by population",
                                "What's the coverage summary?"
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

                {messages.map((msg, i) => (
                    <div
                        key={i}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div
                            className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm ${msg.role === 'user'
                                ? 'bg-indigo-600 text-white rounded-br-md'
                                : 'bg-gray-100 text-gray-800 rounded-bl-md'
                                }`}
                        >
                            {msg.role === 'assistant' ? (
                                <div className="text-sm markdown-body">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                            ul: ({ node, ...props }) => <ul className="list-disc pl-4 my-1" {...props} />,
                                            ol: ({ node, ...props }) => <ol className="list-decimal pl-4 my-1" {...props} />,
                                            li: ({ node, ...props }) => <li className="my-0.5" {...props} />,
                                            p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                                            strong: ({ node, ...props }) => <strong className="font-semibold" {...props} />,
                                            a: ({ node, ...props }) => <a className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
                                            code: ({ node, ...props }) => <code className="bg-gray-200 px-1 py-0.5 rounded text-xs font-mono" {...props} />
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

                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
                            <div className="flex gap-1">
                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                        </div>
                    </div>
                )}

                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                        {error}
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-gray-200 bg-gray-50">
                <div className="flex gap-2">
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={apiKey ? "Ask about your data..." : "Enter API key first..."}
                        disabled={!apiKey || isLoading}
                        className="flex-1 px-4 py-2.5 text-sm border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
                    />
                    <button
                        onClick={handleSendMessage}
                        disabled={!input.trim() || !apiKey || isLoading}
                        className="px-4 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}
