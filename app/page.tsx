import ChatPane from "./components/ChatPane";
import HamsterPane from "./components/HamsterPane";

export default function Home() {
  return (
    <main className="flex h-screen">
      <div className="w-1/2 border-r border-zinc-800">
        <ChatPane />
      </div>
      <div className="w-1/2 flex items-center justify-center">
        <HamsterPane />
      </div>
    </main>
  );
}
