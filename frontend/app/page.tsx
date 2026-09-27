import TodoApp from "@/components/todo-app";

// "use client" が無いので Server Component。見出しのような動かない部分はサーバーで HTML にし、
// 操作が要る部分だけを Client Component（TodoApp）に切り出す。
export default function Home() {
  return (
    <main className="mx-auto w-full max-w-xl px-4 py-12">
      <h1 className="mb-2 text-2xl font-semibold">TODO</h1>
      {/* 認証が無く、公開環境では全員が同じ一覧を共有するため、見た人に前提を伝える。 */}
      <p className="text-sm text-zinc-500">
        デモ用のため、誰でも追加・編集・削除できます。個人情報は入力しないでください。
      </p>
      {/* ポートフォリオとして公開しているので、画面から構成の説明（README・ADR）に辿れるようにする。 */}
      <p className="mb-8 text-sm text-zinc-500">
        ソースコードと設計の説明:{" "}
        {/* target="_blank" で別タブに開く。rel="noopener noreferrer" は、開いた先のページから
            この画面を操作されないようにし、どこから来たかも送らない指定。 */}
        <a
          href="https://github.com/wolf4032/todo-fastapi"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          github.com/wolf4032/todo-fastapi
        </a>
      </p>
      <TodoApp />
    </main>
  );
}
