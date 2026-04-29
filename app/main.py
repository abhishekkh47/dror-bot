from fastapi import FastAPI
from app.api.routes import router
from app.core.flow_loader import FlowLoader

app = FastAPI()

flow_loader = FlowLoader()
flow_loader.load_flows()

app.include_router(router)