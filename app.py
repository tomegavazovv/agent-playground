from dotenv import load_dotenv
_ = load_dotenv()

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage, ToolCall
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import asyncio
import json
import streamlit as st
import random
import uuid
from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.tracers import LangChainTracer
memory = MemorySaver()



def scrape_agency_tool(agency_url: str) -> str:
    """
    Scrape an Upwork agency profile page.
    
    Args:
        agency_url (str): The full URL of the Upwork agency profile to scrape
        
    Returns:
        str: A stringified dictionary of the scraped agency data
    """
    print(f"Scraping agency URL: {agency_url}")
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept-Encoding': None,  
    }

    try:
        response = cffi_requests.get(agency_url, headers=headers, impersonate="chrome110")
        response.raise_for_status()
        
        # Use 'html.parser' without specifying encoding
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract data using BeautifulSoup
        title_element = soup.select_one('h4.agency-title span.vertical-align-middle')
        description_element = soup.select_one('.overflow-wrap-anywhere p.white-space-pre-wrap')
        services = soup.select('.air3-card-sections > .air3-card-section h5')
        skills = soup.select('.air3-token-wrap > .air3-token')
        
        # Find hourly rate
        hourly_rate_label = None
        for small in soup.find_all('small'):
            if small.get_text().strip() == 'Hourly rate':
                hourly_rate_label = small
                break
        
        hourly_rate = ''
        if hourly_rate_label:
            rate_container = hourly_rate_label.find_parent('div')
            if rate_container:
                rate_element = rate_container.find('h4')
                if rate_element:
                    hourly_rate = rate_element.get_text().strip()
        
        agency_data = {
            'title': title_element.get_text().strip() if title_element else '',
            'description': description_element.get_text().strip() if description_element else '',
            'services': [service.get_text().strip() for service in services],
            'skills': [skill.get_text().strip() for skill in skills],
            'hourlyRate': hourly_rate
        }
        
        # Convert the dictionary to a formatted string
        formatted_data = (
            f"Agency Title: {agency_data['title']}\n"
            f"Description: {agency_data['description']}\n"
            f"Services: {', '.join(agency_data['services'])}\n"
            f"Skills: {', '.join(agency_data['skills'])}\n"
            f"Hourly Rate: {agency_data['hourlyRate']}"
        )
        
        return formatted_data
    except ImportError:
        raise ImportError("curl_cffi not installed")
    except Exception as e:
        return str(e), 500

tavily_tool = TavilySearchResults(max_results=4) #increased number of results

tools = [scrape_agency_tool, tavily_tool]

from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field, RootModel
category_types = [
  'Web Development',
  'Mobile Development',
]
experience_level_types = ['Entry Level', 'Mid Level', 'Senior Level']

from typing import List
from enum import Enum
from pydantic import BaseModel, Field

class ScrapedKnowledgeState(BaseModel):
    categories: Dict[str, Optional[bool]] = Field(
        default_factory=lambda: {category: None for category in category_types},
        description="Dictionary of professional categories extracted from agency profile"
    )
    experience_level: Dict[str, Optional[bool]] = Field(
        default_factory=lambda: {level: None for level in experience_level_types},
        description="Dictionary of experience levels extracted from agency profile"
    )
    min_hourly_rate: Optional[float] = Field(
        default=None,
        description="Minimum hourly rate from agency profile"
    )
    fixed_price_min: Optional[float] = Field(
        default=None,
        description="Minimum fixed price from agency profile"
    )

    class Config:
        json_schema_extra = {
            "required": ["categories", "experience_level", "min_hourly_rate", "fixed_price_min"]
        }

class UserPreferencesState(BaseModel):
    project_duration: Optional[float] = Field(
        default=None,
        description="Minimum project duration that the agency is willing to accept"
    )
    average_client_spent: Optional[float] = Field(
        default=None,
        description="Minimum total amount in USD that a client has spent on Upwork"
    )
    hourly_workload: Optional[float] = Field(
        default=None,
        description="Minimum number of hourly workload that the client needs"
    )
    is_it_a_company: Optional[bool] = Field(
        default=None,
        description="Indicates whether the client is a company or a freelancer"
    )

class KnowledgeState(ScrapedKnowledgeState, UserPreferencesState):
    """Combined state that includes both scraped data and user preferences"""
    pass

class RouteDecision(str, Enum):
    HAS_UPWORK_URL = "has_upwork_url"
    HAS_NEW_KNOWLEDGE = "has_new_knowledge"
    CONTINUE_CONVERSATION = "continue_conversation"

class RouterOutput(BaseModel):
    decision: RouteDecision = Field(
        description="The routing decision based on message analysis"
    )
    reasoning: str = Field(
        description="Brief explanation of why this route was chosen"
    )
    tool_call: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tool call needed to be executed if decision is has_upwork_url"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "decision": "has_upwork_url",
                    "reasoning": "Message contains an Upwork agency URL that needs to be scraped",
                    "tool_call": {
                        "name": "scrape_agency",
                        "args": "https://www.upwork.com/agencies/1231321312"
                    }
                }
            ]
        }

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    knowledge: Annotated[KnowledgeState, lambda x, y: KnowledgeState(**{
        **x.model_dump(),
        **{
            k: v for k, v in y.model_dump().items() 
            if v is not None  # Only include non-None values
            and (
                not isinstance(v, dict)  # For simple fields
                or any(val is not None for val in v.values())  # For dict fields with any non-None values
            )
        }
    })]
    route_decision: Optional[RouterOutput] = None

extract_knowledge_prompt = """
You are an expert at extracting knowledge from a conversation.

This is the current knowledge state that we have about an agency that searches for jobs on Upwork:
{current_knowledge}

If you think that the most recent interactions contain new information that is not in the current knowledge state, please extract it and update the knowledge state.
{last_interactions}

1. If the user gives any clear affirmative response ("yes", "yeah", "correct", "we do", etc.) to a specific category question = set that category to true
2. If the user gives any clear negative response ("no", "nope", "we don't", etc.) to a specific category question = set that category to false
3. For experience level responses:
   - Set 'senior' to true if they mention: "expert", "senior", "experienced", "specialists", "professionals", or indicate high expertise
   - Set 'midLevel' to true if they mention: "intermediate", "mid-level", or indicate moderate expertise
   - Set 'entryLevel' to true if they mention: "junior", "entry-level", "beginner", or indicate basic expertise
   - Multiple levels can be true if indicated
4. If the response is ambiguous or doesn't address a category = leave it as null

VERY IMPORTANT: 
- Return only the fields that are updated in the last interactions
- Only modify fields that are explicitly addressed in the last interactions
- Keep ALL existing values for fields not mentioned in the response
"""

extract_scraped_knowledge_prompt = """
You are an expert at extracting knowledge from content scraped from Upwork agency profiles that is given to you in JSON format. 

This is the current knowledge state:
{current_knowledge}

Scraped Content in JSON format:
{scraped_content}

1. If the data explicitly mentions or shows evidence of offering a service category = set that category to true
2. If the profile doesn't mention or show any evidence of a service category = set that category to false
3. If the json object context even slightly suggests that the agency is senior level = set 'senior' to true, the same for mid. This should be nearly impossible to miss.

Important: The absence of a service category in the profile should be interpreted as false, as agencies typically list all services they offer.

Also important: Include all the fields that you have in the current knowledge state to the new knowledge state. Keep existing values for any fields not present in the scraped data
"""

system_prompt = f"""You are the Onboarding AI Agent. Your role is to guide a new freelancer through an interactive onboarding process in a friendly, concise, and slightly humorous tone. 
Your objective is to gather and confirm all data required by the following schema:

{KnowledgeState()}

IMPORTANT: If the user provides ANY URL containing "upwork.com", IMMEDIATELY use the scrape_agency tool to analyze it before proceeding with other questions.

Conversation Goals:
1. Greet the user and briefly explain your purpose: to capture their preferences and qualifications for matching them with suitable job listings.
2. Actively look for and process any Upwork URLs in user messages:
   - If a URL containing "upwork.com" is found, IMMEDIATELY call scrape_agency
   - After scraping, acknowledge the results and continue the conversation
3. Gather details for each part of the schema:
   - Use scraped data as a starting point
   - Ask for confirmation or additional details for any missing information
4. Confirm each piece of information as it's provided and check if more details are needed
5. If none of the fields are None, finish the conversation with "Thank you for your time and cooperation. We will get back to you with the best job listings shortly."

Conversation Style:
- Use short, friendly messages with a touch of humor to keep the user engaged
- Guide the user step by step, clarifying and refining entries as needed
- Recursively prompt the user until all data is correctly collected
- ALWAYS check for and process Upwork URLs before asking any other questions
"""

router_prompt = """
You are an expert at analyzing conversations and determining if they contain new information about a knowledge state.
The knowledge state represents the current state of knowledge about an agency that searches for jobs on Upwork.

Analyze the last interactions and determine if it contains some new information about this knowledge state:

Current knowledge state:
{current_knowledge}

Most recent interactions:
{recent_interactions}

Analyze the messages and determine the appropriate route based on these criteria:
1. If the message contains an Upwork URL (example: https://www.upwork.com/agencies/1231321312), choose HAS_UPWORK_URL and provide the tool call
2. If the message contains new information about:
   - Professional categories they work in
   - Experience levels
   - Pricing/rates
   - Or any other relevant business information
   Then choose HAS_NEW_KNOWLEDGE
3. If the message is a general response without new information, choose CONTINUE_CONVERSATION

Provide your decision and a brief explanation of why you chose it.
"""

follow_up_prompt = """
You are an expert at asking follow-up questions to help set up job feed filters on Upwork.

This is the current filter state we have configured for the agency's Upwork job feed:
{current_knowledge}

Most recent interactions for context:
{last_interactions}

FIRST STEP - Check if all fields have values:
1. Check project_duration is not None
2. Check average_client_spent is not None
3. Check hourly_workload is not None
4. Check is_it_a_company is not None

If ANY of these fields are None:
- Ask about 1-2 missing fields using the style guide below
- Focus on the fields that are still None

IMPORTANT: If ALL fields have values (not one is None):
- Respond with: "Perfect! We have all the information needed to optimize your job feed 🎯. Let me know if you'd like to update any preferences!"
- Do not ask any additional questions

Style Guide (only if fields are missing):
- Be concise and direct while maintaining a friendly tone
- Frame questions as job feed preferences
- Make it clear these settings will affect which jobs they see
- Use fun transitions like "Awesome sauce!" or other creative slang
- Keep it light and enjoyable

Remember: If ALL fields above show actual values (not None), you MUST stop asking questions!
"""



class Agent:
    def __init__(self, model, tools, checkpointer=None, system=""):
        test_model = BaseChatOpenAI(
            model="deepseek-chat",
            openai_api_key="sk-8e128b8744524265be579501612ee5c1",
            openai_api_base="https://api.deepseek.com",
            max_tokens=1024
        )

        self.system = system
        self.extraction_from_interaction_llm = test_model.with_structured_output(KnowledgeState, method="function_calling")
        self.extraction_from_scraped_content_llm = test_model.with_structured_output(ScrapedKnowledgeState, method="function_calling")
        self.router_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo").with_structured_output(RouterOutput, method="function_calling")
        self.follow_up_llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")
        
        graph = StateGraph(AgentState)
        graph.add_node("router", self.route_message)
        graph.add_node("llm", self.call_openai)
        graph.add_node("scrape_agency", self.scrape_agency)
        graph.add_node("extract_knowledge", self.extract_knowledge)
        graph.add_node("ask_follow_up", self.ask_follow_up)
        graph.add_conditional_edges(
            "router",
            self.determine_route,
            {
                "has_upwork_url": "scrape_agency",
                "has_new_knowledge": "extract_knowledge", 
                "continue_conversation": "llm"
            }
        )

        graph.add_edge("scrape_agency", "extract_knowledge")
        graph.add_edge("llm", END)
        graph.add_edge("extract_knowledge", 'ask_follow_up')
        graph.add_edge('ask_follow_up', END)
        
        graph.set_entry_point("router")
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model

    def call_openai(self, state: AgentState, config: RunnableConfig):
        messages = state['messages']
        if self.system:
            if self.system and not any(isinstance(m, SystemMessage) for m in messages):
                messages = [SystemMessage(content=self.system)] + messages
                
        message = self.model.invoke(messages, config=config)
        return {'messages': [message]}

    def route_message(self, state: AgentState):
        recent_interactions = state['messages'][-2:]
        route_decision = self.router_llm.invoke(
            router_prompt.format(
                current_knowledge=state['knowledge'].model_dump(),
                recent_interactions=recent_interactions
            )
        )
        return {"route_decision": route_decision}

    def determine_route(self, state: AgentState) -> str:
        return state['route_decision'].decision

    def extract_knowledge(self, state: AgentState):
        last_interactions = [{"role": x.type, "content": x.content} for x in state['messages'][-2:]]  # Fixed: using list comprehension instead of .map()
        current_knowledge = state['knowledge']
        was_upwork_scraped = False

        if any(isinstance(m, ToolMessage) for m in state['messages'][-2:]):
            was_upwork_scraped = True
        
        if was_upwork_scraped:
            prompt = extract_scraped_knowledge_prompt.format(
                current_knowledge=current_knowledge.model_dump_json(), # Changed from model_dump() to model_dump_json()
                scraped_content=last_interactions[-1]
            )
            new_knowledge = self.extraction_from_scraped_content_llm.invoke(prompt)
        else:
            prompt = extract_knowledge_prompt.format(
                current_knowledge=current_knowledge.model_dump_json(), # Changed from model_dump() to model_dump_json()
                last_interactions=last_interactions
            )
            new_knowledge = self.extraction_from_interaction_llm.invoke(prompt)
        
        return {'knowledge': new_knowledge}
        
            
    def ask_follow_up(self, state: AgentState):
        message = self.follow_up_llm.invoke(follow_up_prompt.format(
            current_knowledge=state['knowledge'].model_dump(),
            last_interactions=state['messages'][-2:]
        ))

        return {'messages': [message]}
        

    def exists_action(self, state: AgentState):
        result = state['messages'][-1]
        return len(result.tool_calls) > 0

    def scrape_agency(self, state: AgentState):
        url = state['route_decision'].tool_call['args']
        result = scrape_agency_tool(url)
        return {'messages': [ToolMessage(tool_call_id=str(uuid.uuid4()), name='scrape_agency', content=str(result))]}

    def take_action(self, state: AgentState):
        tool_calls = state['messages'][-1].tool_calls

        results = []
        for t in tool_calls:
            print(f"Calling: {t}")
            result = self.tools[t['name']].invoke(t['args'])
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
        print("Back to the model!")
        return {'messages': results}



# async def chat(message: str, knowledge: KnowledgeState=None):
#     input_message = HumanMessage(content=message)
#     if knowledge:
#         state = {"messages": [*messages, input_message], "knowledge": knowledge}
#     else:
#         state = {"messages": [*messages, input_message]}
    
#     async for event in abot.graph.astream_events(state, config, version="v2"):
#         kind = event["event"]
#         if kind == "on_chat_model_stream":
#             content = event["data"]["chunk"].content
#             print(content, end="", flush=True)

# asyncio.run(chat("hi! I'm Lance", knowledge=KnowledgeState()))

async def stream_response(state, config, response_placeholder, abot):
    response = ""
    was_tool_displayed = False
    was_extraction_displayed = False
    async for event in abot.graph.astream_events(state, config, version="v2"):
        if event["event"] == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            response += content
            response_placeholder.markdown(response)
        elif event["event"] == "on_chain_start":
            try:
                if not was_tool_displayed and event["data"]["input"]["route_decision"].tool_call:
                    response += "\n\nscraping agency...\n\n"
                    response_placeholder.markdown(response)
                    was_tool_displayed = True
                if not was_extraction_displayed and event['name'] == 'extract_knowledge':
                    response += "\n\nUpdating knowledge 🧠✨ ...\n\n If this takes too long, it is deepseek's fault, not mine. Sometimes they suck ☭ 🇨🇳\n\n"
                    response_placeholder.markdown(response)
                    was_extraction_displayed = True
            except:
                pass
    return response

def main():
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    abot = Agent(model, [], system=system_prompt, checkpointer=memory)
    st.set_page_config(layout="wide")

    # Add custom CSS for the chat container with fixed input at bottom
    st.markdown("""
        <style>
        .st-key-chat-container {
            display: flex;
            flex-direction: column;
            height: calc(100vh - 100px);
            position: relative;
        }
        .st-key-chat-messages {
            flex-grow: 1;
            overflow-y: auto;
            padding: 1rem;
            margin-bottom: 80px; /* Space for input */
        }
        .st-key-chat-input {
            position: fixed;
            bottom: 0;
            left: 10;
            right: 15;
            width: 100%; /* Match the chat column width */
            background-color: white;
            padding: 1rem;
            border-top: 1px solid #ddd;
            z-index: 1000;
        }
        .st-key-knowledge-state {
            height: calc(100vh - 100px);
            overflow-y: auto;
            padding: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("Upwork Agency Onboarding Assistant")
    st.markdown("Don't try to break me, cause you probably will. Answer what I am asking")

    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "knowledge" not in st.session_state:
        st.session_state.knowledge = KnowledgeState()
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    
    # Create two columns
    chat_col, knowledge_col = st.columns([0.6, 0.4])
    
    # Left column - Chat UI
    with chat_col:
        with st.container(key="chat-container", height=600):
            # Chat messages container
            chat_messages = st.container()
            
            with chat_messages:
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
            
            # Chat input at the bottom
            prompt = st.chat_input("Type your message here...", key="chat-input")
            
            if prompt:
                # Rest of the chat logic remains the same
                st.session_state.messages.append({"role": "user", "content": prompt})
                
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                state = {
                    "messages": [HumanMessage(content=msg["content"]) for msg in st.session_state.messages],
                    "knowledge": st.session_state.knowledge
                }
                
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    response = asyncio.run(stream_response(state, config, response_placeholder, abot))
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                agent_state = abot.graph.get_state(config)
                updated_knowledge = agent_state.values['knowledge']
                st.session_state.knowledge = updated_knowledge
                
                st.rerun()
    
    # Right column - Knowledge State
    with knowledge_col:
        with st.container(key="knowledge-container", height=600):
            st.header("Current Knowledge State")
            st.json(st.session_state.knowledge.model_dump())

if __name__ == "__main__":
    main()