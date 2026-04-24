"use client";

import { use } from "react";
import { ContextPanel } from "@/components/context/ContextPanel";
import { useRouter } from "next/navigation";

export default function ChatContextPage({ params }: { params: Promise<{ chat_id: string }> }) {
  const { chat_id } = use(params);
  const router = useRouter();

  return (
    <div className="h-screen bg-zinc-950 p-4">
      <div className="max-w-6xl mx-auto h-full">
        <ContextPanel
          chatId={chat_id}
          onClose={() => router.back()}
        />
      </div>
    </div>
  );
}
