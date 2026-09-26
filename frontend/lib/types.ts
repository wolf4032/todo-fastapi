// backend/app/schemas/todo.py と対応させる。型は実行時には消えるので、
// API が本当にこの形を返すかは保証されない（手で揃えている）。
// datetime は JSON では ISO 8601 の文字列として届くので string で受ける。

export type Todo = {
  id: number;
  title: string;
  description: string | null;
  due_date: string | null;
  is_completed: boolean;
  created_at: string;
  updated_at: string;
};

export type TodoCreate = {
  title: string;
  // `?:` は「キーごと省略できる」。省略すると API 側の既定値（None）になる。
  description?: string | null;
  due_date?: string | null;
};

// PATCH は送ったキーだけが更新される（exclude_unset）ので、全キーを省略可にする。
// Partial<T> は T の全プロパティに `?` を付けた型を作る。
export type TodoUpdate = Partial<
  Pick<Todo, "title" | "description" | "due_date" | "is_completed">
>;

export type TodoListResponse = {
  items: Todo[];
  total: number;
  limit: number;
  offset: number;
};

// backend/app/core/exceptions.py の _error_response が返す形。
export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details?: unknown;
  };
};
