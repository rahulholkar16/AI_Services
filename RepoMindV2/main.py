from fastapi import FastAPI;
from fastapi.middleware.cors import CORSMiddleware;
from contextlib import asynccontextmanager;

@asynccontextmanager
async def lifespan (app: FastAPI):
    print("Application is Start>>>");
    """
    Here we setup DB connetion.
    and Agent Intialization.
    """
    yield

    print("Application is Stoped");
    """
        We close the DB connection and Agent and Other temp memory.
    """

app = FastAPI(lifespan=lifespan);

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def main ():
    return { "status": "ok" }