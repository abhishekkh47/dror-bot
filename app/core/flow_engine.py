from .flow_loader import FlowLoader
from .session_store import SessionStore
from .types import Step

class FlowEngine: 
    def __init__(self, flow_loader: FlowLoader, session_store: SessionStore):
        self.flow_loader = flow_loader
        self.session_store = session_store
    
    def start_flow(self, flow_id: str):
        flow = self.flow_loader.get_flow(flow_id)
        first_step = flow.steps[0]
        return self.session_store.create(flow_id, first_step.id)
    
    def get_current_step(self, session_id: str) -> Step:
        session = self.session_store.get(session_id)
        flow = self.flow_loader.get_flow(session.flow_id)
        return flow.get_step(session.current_step)
    
    def process_input(self, session_id: str, user_input: str) -> Step:
        session = self.session_store.get(session_id)
        flow = self.flow_loader.get_flow(session.flow_id)

        current_step = flow.get_step(session.current_step)

        if current_step.type == 'DECISION':
            normalized_input = self.normalize_input(user_input)
            if normalized_input not in current_step.options:
                raise Exception("Invalid Option")
            
            next_step_id = current_step.next[normalized_input]
        else:
            next_step_id = current_step.next
        
        if not next_step_id:
            raise Exception("Flow ended")
        
        session.history.append(current_step.id)
        session.current_step = next_step_id

        self.session_store.update(session)
        return flow.get_step(next_step_id)
    
    def normalize_input(self, user_input: str) -> str:
        return user_input.lower().strip()