from pydantic import BaseModel

class TechStack(BaseModel):
    frontend: str | None = None
    backend: str | None = None
    database: str | None = None
    orm: str | None = None
    authentication: str | None = None
    state_management: str | None = None
    styling: str | None = None
    deployment: str | None = None

class ArchitectureReport(BaseModel):
    project_overview: str
    architecture: str
    modules: list[str]
    data_flow: str
    authentication_flow: str
    database_flow: str
    api_flow: str