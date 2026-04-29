import json
from pathlib import Path
from .types import Flow

class FlowLoader:
    def __init__(self):
        self.flows = {}
    
    def load_flows(self):
        path = Path("app/data/flows/payment_execution.json")
        data = json.loads(path.read_text())
        flow = Flow(**data)
        self.flows[flow.flow_id] = flow
    
    def get_flow(self, flow_id: str) -> Flow:
        if flow_id not in self.flows:
            raise Exception("Flow not found")
        return self.flows[flow_id]