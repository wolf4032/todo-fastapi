from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 値はすべて環境変数から読む（12-factor）。イメージにパスワードを焼き込まない。
    # → docs/notes/step-05-app-foundation.md
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


# モジュール import 時に一度だけ生成し、アプリ全体で使い回す。
settings = Settings()
