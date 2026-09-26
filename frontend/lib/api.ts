import type {
  ApiErrorBody,
  Todo,
  TodoCreate,
  TodoListResponse,
  TodoUpdate,
} from "@/lib/types";

// 相対パスなので、ブラウザは今開いているオリジン（localhost:3000）へ送る。
// そこから api コンテナへは next.config.ts の rewrites が中継する。
const BASE_URL = "/api/v1";

// 画面側が「どのエラーか」を status や code で判別できるよう、専用のクラスにする。
// status 0 は HTTP の応答自体が得られなかった（接続できなかった）ことを表す。
export class ApiError extends Error {
  constructor(
    // コンストラクタ引数に readonly を付けると、同名のプロパティの宣言と代入を兼ねる（TypeScript の記法）。
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId: string | null = null,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  // web コンテナが api に繋がらないときは Next.js 自身が 500 を返し、本文は JSON ではない。
  // 決めた形で返ってくるとは限らないので、読めなければ汎用のメッセージにする。
  try {
    const body = (await res.json()) as ApiErrorBody;
    const { code, message, request_id, details } = body.error;
    return new ApiError(res.status, code, message, request_id, details);
  } catch {
    return new ApiError(res.status, "unknown_error", `HTTP ${res.status}`);
  }
}

// <T> は型引数。呼び出し側が「成功時の本文の型」を指定する。
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers:
        init.body === undefined
          ? init.headers
          : { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    // fetch が reject するのは応答を受け取れなかったときだけ。4xx/5xx は reject されない。
    throw new ApiError(0, "network_error", "サーバーに接続できません");
  }
  if (!res.ok) {
    throw await toApiError(res);
  }
  // 204 No Content は本文が空なので、json() を呼ぶと失敗する。
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export function listTodos(limit = 100): Promise<TodoListResponse> {
  return request(`/todos?limit=${limit}`);
}

export function createTodo(data: TodoCreate): Promise<Todo> {
  return request("/todos", { method: "POST", body: JSON.stringify(data) });
}

export function updateTodo(id: number, data: TodoUpdate): Promise<Todo> {
  return request(`/todos/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteTodo(id: number): Promise<void> {
  return request(`/todos/${id}`, { method: "DELETE" });
}

// 画面に出す1行の文言にする。422 は FastAPI（Pydantic）の details に
// 項目ごとの理由が入っているので、それを並べる。
export function errorMessage(e: unknown): string {
  if (!(e instanceof ApiError)) {
    return "予期しないエラーが発生しました";
  }
  if (e.status === 422 && Array.isArray(e.details)) {
    const reasons = e.details.map(
      (d: { loc?: unknown[]; msg?: string }) =>
        // loc は ["body", "title"] のような位置情報。先頭の "body" は省く。
        `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`,
    );
    return `${e.message}（${reasons.join(" / ")}）`;
  }
  return e.message;
}
