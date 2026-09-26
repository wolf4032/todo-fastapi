import TodoApp from "@/components/todo-app";

// "use client" が無いので Server Component。見出しのような動かない部分はサーバーで HTML にし、
// 操作が要る部分だけを Client Component（TodoApp）に切り出す。
export default function Home() {
  return (
    <main className="mx-auto w-full max-w-xl px-4 py-12">
      <h1 className="mb-8 text-2xl font-semibold">TODO</h1>
      <TodoApp />
    </main>
  );
}
