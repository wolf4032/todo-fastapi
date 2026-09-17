import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_todo(client: AsyncClient) -> None:
    create_res = await client.post("/api/v1/todos", json={"title": "牛乳を買う"})
    assert create_res.status_code == 201
    todo_id = create_res.json()["id"]

    get_res = await client.get(f"/api/v1/todos/{todo_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "牛乳を買う"


@pytest.mark.asyncio
async def test_get_missing_todo_returns_404(client: AsyncClient) -> None:
    res = await client.get("/api/v1/todos/999999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_with_empty_title_returns_422(client: AsyncClient) -> None:
    res = await client.post("/api/v1/todos", json={"title": ""})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_list_todos_with_pagination_and_filter(client: AsyncClient) -> None:
    for i in range(3):
        await client.post("/api/v1/todos", json={"title": f"todo-{i}"})

    page_res = await client.get("/api/v1/todos", params={"limit": 2, "offset": 1})
    page_body = page_res.json()
    assert page_res.status_code == 200
    assert page_body["total"] == 3
    assert len(page_body["items"]) == 2

    filtered_res = await client.get("/api/v1/todos", params={"is_completed": True})
    assert filtered_res.json()["items"] == []


@pytest.mark.asyncio
async def test_update_and_delete_todo(client: AsyncClient) -> None:
    create_res = await client.post("/api/v1/todos", json={"title": "牛乳を買う"})
    todo_id = create_res.json()["id"]

    # exclude_unset=True が効いていれば is_completed 以外は変わらないはず。
    patch_res = await client.patch(
        f"/api/v1/todos/{todo_id}", json={"is_completed": True}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "牛乳を買う"
    assert patch_res.json()["is_completed"] is True

    delete_res = await client.delete(f"/api/v1/todos/{todo_id}")
    assert delete_res.status_code == 204

    after_delete_res = await client.get(f"/api/v1/todos/{todo_id}")
    assert after_delete_res.status_code == 404
