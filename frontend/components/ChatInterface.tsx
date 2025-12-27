"use client";

import { useState, useRef, useEffect, FormEvent, ChangeEvent } from "react";
import { Send, Bot, User, FileText, Loader2, Check, Paperclip } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Configuration
const API_BASE_URL = "http://localhost:8001";

// Types
type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  tools?: string[];
};

export default function ChatInterface() {
  // --- STATE ---
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  // Create a persistent session ID
  const [sessionId] = useState(() => "session-" + Math.random().toString(36).substr(2, 9));

  // --- REFS ---
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- EFFECTS ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --- HANDLERS ---
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    // Optimistic Update
    const userMsg: Message = { id: Date.now().toString(), role: "user", content: input };
    const agentMsgId = (Date.now() + 1).toString();
    const agentPlaceholder: Message = { id: agentMsgId, role: "agent", content: "", tools: [] };
    
    setMessages((prev) => [...prev, userMsg, agentPlaceholder]);
    const currentInput = input;
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
            message: currentInput,
            session_id: sessionId 
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; 

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== agentMsgId) return msg;

                if (data.type === "agent") {
                  return { ...msg, content: msg.content + data.content };
                }

                if (data.type === "tool") {
                  const currentTools = msg.tools || [];
                  if (currentTools.includes(data.content)) return msg;
                  return { ...msg, tools: [...currentTools, data.content] };
                }

                return msg;
              })
            );
          } catch (e) { console.error("Stream parse error:", e); }
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => prev.map(msg => 
        msg.id === agentMsgId ? { ...msg, content: msg.content + "\n❌ Error: Connection failed." } : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    const file = e.target.files[0];
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE_URL}/upload`, {
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) throw new Error("Upload failed");
      
      const data = await res.json();
      setInput(`Read ${data.filename} and create a proposal based on its requirements.`);
      
    } catch (error) {
      alert("Failed to upload file.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col w-full h-full bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
      
      {/* Header */}
      <div className="bg-slate-900 p-4 flex items-center gap-3 shrink-0">
        <div className="p-2 bg-blue-600 rounded-lg shadow-lg shadow-blue-900/20">
            <Bot className="text-white w-5 h-5" />
        </div>
        <div>
          <h2 className="text-white font-bold text-base tracking-wide">Enterprise AI Assistant</h2>
          <p className="text-slate-400 text-xs font-medium">Powered by LangGraph & MCP</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-8 bg-slate-50 scroll-smooth">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-6 animate-in fade-in duration-500">
            <div className="w-24 h-24 bg-white rounded-full flex items-center justify-center shadow-sm border border-slate-100">
                <FileText className="w-12 h-12 text-blue-500" />
            </div>
            <div className="space-y-2">
                <h3 className="text-2xl font-semibold text-slate-800">Ready to Assist</h3>
                <p className="text-slate-500 max-w-md text-sm">
                    Upload a complex RFP document or ask deep technical research questions. 
                </p>
            </div>
          </div>
        )}

        {messages.map((msg, index) => {
           const isLastMessage = index === messages.length - 1;
           const isProcessing = isLastMessage && isLoading;
           
           return (
            <div key={msg.id} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 shadow-sm ${msg.role === "user" ? "bg-blue-600" : "bg-emerald-600"}`}>
                {msg.role === "user" ? <User className="w-6 h-6 text-white" /> : <Bot className="w-6 h-6 text-white" />}
              </div>

              <div className={`max-w-[75%] space-y-2`}>
                
                {/* TOOL USAGE BADGES */}
                {msg.tools && msg.tools.length > 0 && (
                  <div className="flex flex-col gap-2 mb-3">
                    {msg.tools.map((tool, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-xs font-semibold text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-full w-fit shadow-sm">
                        {isProcessing ? <Loader2 className="w-3 h-3 animate-spin text-blue-500" /> : <Check className="w-3 h-3 text-emerald-600" />}
                        {/* REVERTED: Now shows full string "Accessed Tool: read_file" */}
                        <span className="uppercase tracking-wider text-[10px]">{tool}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className={`p-6 rounded-2xl shadow-sm overflow-x-auto prose prose-sm max-w-none ${
                    msg.role === "user" 
                      ? "bg-blue-600 text-white rounded-tr-none prose-invert" 
                      : "bg-white text-slate-800 border border-gray-100 rounded-tl-none ring-1 ring-slate-900/5"
                  }`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                </div>
              </div>
            </div>
           );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area (Reduced Padding from p-6 to p-4) */}
      <form onSubmit={handleSubmit} className="p-4 bg-white border-t border-gray-100 flex gap-4 items-center shrink-0">
        <input 
          type="file" 
          ref={fileInputRef}
          onChange={handleFileSelect}
          accept=".pdf"
          className="hidden"
        />
        
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || isUploading}
          className="p-4 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all duration-200 border border-transparent hover:border-blue-100 disabled:opacity-50"
          title="Upload RFP PDF"
        >
          {isUploading ? <Loader2 className="w-6 h-6 animate-spin text-blue-600" /> : <Paperclip className="w-6 h-6" />}
        </button>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question or upload a document..."
          className="flex-1 p-4 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-slate-800 placeholder-slate-400 transition-all"
          disabled={isLoading}
        />
        
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="bg-blue-600 hover:bg-blue-700 text-white p-4 rounded-xl transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
        >
          {isLoading ? <Loader2 className="w-6 h-6 animate-spin" /> : <Send className="w-6 h-6" />}
        </button>
      </form>
    </div>
  );
}