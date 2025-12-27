import ChatInterface from "@/components/ChatInterface";

export default function Home() {
  return (
    // Outer container: Centers the app and adds a subtle background
    <main className="flex min-h-screen items-center justify-center bg-gray-100 p-4">
      
      {/* Size Controller: 
         - w-[98%]: Takes up 98% of width on small screens
         - max-w-[1800px]: Stops growing on huge monitors (looks pro)
         - h-[92vh]: Takes up 92% of the viewport height (tall!)
      */}
      <div className="w-[98%] max-w-[1800px] h-[92vh]">
        <ChatInterface />
      </div>
    </main>
  );
}