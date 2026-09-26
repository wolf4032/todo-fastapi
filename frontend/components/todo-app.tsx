// このファイルから下（import したものを含む）がブラウザに送られる JavaScript になる。
// state・イベントハンドラ・useEffect はブラウザでしか動かないので必要。
// → docs/notes/step-15-todo-page.md
"use client";

import { type FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  createTodo,
  deleteTodo,
  errorMessage,
  listTodos,
  updateTodo,
} from "@/lib/api";
import type { Todo } from "@/lib/types";

export default function TodoApp() {
  // useState は「値が変わったら画面を描き直す」変数。[現在の値, 更新関数] の組を返す。
  const [todos, setTodos] = useState<Todo[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 第2引数の [] は「最初に画面に出たときだけ実行する」指定。
  useEffect(() => {
    // アンマウント（画面の構成から外れること。開発時の Strict Mode による再実行を含む）の後に届いた応答で
    // state を書き換えないためのフラグ。return した関数は後片付けとして呼ばれる。
    let ignore = false;
    listTodos()
      .then((res) => {
        if (ignore) return;
        setTodos(res.items);
        setTotal(res.total);
      })
      .catch((e: unknown) => {
        if (!ignore) setError(errorMessage(e));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, []);

  function removeLocally(id: number) {
    // 更新関数に関数を渡すと、直前の値（prev）を受け取って次の値を返せる。
    setTodos((prev) => prev.filter((t) => t.id !== id));
    setTotal((prev) => prev - 1);
  }

  // 他のタブや curl で先に消されていた場合。サーバーに無いものは画面からも消す。
  function handleNotFound(e: unknown, id: number): boolean {
    if (e instanceof ApiError && e.status === 404) {
      removeLocally(id);
      setError("この TODO はすでに削除されていました");
      return true;
    }
    return false;
  }

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    // フォーム送信の既定動作（ページ遷移を伴う送信）を止め、fetch で送る。
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const created = await createTodo({ title });
      setTodos((prev) => [...prev, created]);
      setTotal((prev) => prev + 1);
      setTitle("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(todo: Todo) {
    setError(null);
    try {
      const updated = await updateTodo(todo.id, {
        is_completed: !todo.is_completed,
      });
      setTodos((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch (err) {
      if (!handleNotFound(err, todo.id)) setError(errorMessage(err));
    }
  }

  async function handleDelete(id: number) {
    setError(null);
    try {
      await deleteTodo(id);
      removeLocally(id);
    } catch (err) {
      if (!handleNotFound(err, id)) setError(errorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleCreate} className="flex gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="やること"
          required
          className="flex-1 rounded border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-zinc-900 px-4 py-2 text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          追加
        </button>
      </form>

      {/* {条件 && <要素>} は「条件が真のときだけ描画する」JSX の書き方。 */}
      {error && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
        >
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-zinc-500">読み込み中…</p>
      ) : todos.length === 0 ? (
        <p className="text-zinc-500">TODO はありません</p>
      ) : (
        <ul className="flex flex-col divide-y divide-zinc-200 dark:divide-zinc-800">
          {/* key は React が「どの要素がどれか」を追跡するための一意な値。 */}
          {todos.map((todo) => (
            <li key={todo.id} className="flex items-center gap-3 py-2">
              <input
                type="checkbox"
                checked={todo.is_completed}
                onChange={() => handleToggle(todo)}
                aria-label={`${todo.title} を完了にする`}
                className="size-4"
              />
              <span
                className={`flex-1 ${todo.is_completed ? "text-zinc-400 line-through" : ""}`}
              >
                {todo.title}
              </span>
              <button
                onClick={() => handleDelete(todo.id)}
                className="text-sm text-zinc-500 hover:text-red-600"
              >
                削除
              </button>
            </li>
          ))}
        </ul>
      )}

      {total > todos.length && (
        <p className="text-sm text-zinc-500">
          全 {total} 件のうち先頭 {todos.length} 件を表示しています
        </p>
      )}
    </div>
  );
}
